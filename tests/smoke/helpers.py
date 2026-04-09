"""Shared utilities for smoke tests.

Pure functions — no pytest dependency. Used by both standalone-mode tests
(AMM, MPT, trustline) and the consensus-network payment ring test.
"""

import asyncio
import subprocess
import time

import pytest
from xrpl.asyncio.clients import AsyncJsonRpcClient
from xrpl.asyncio.transaction import autofill_and_sign, submit
from xrpl.clients import JsonRpcClient
from xrpl.models import IssuedCurrencyAmount, Payment
from xrpl.models.requests import AccountLines, GenericRequest, ServerInfo, Tx
from xrpl.wallet import Wallet

XRPLD_IMAGE = "rippleci/xrpld:develop"
STARTUP_TIMEOUT = 30

STANDALONE_CFG = """\
[server]
port_rpc_admin_local

[port_rpc_admin_local]
port = 5005
ip = 0.0.0.0
admin = 0.0.0.0
protocol = http

[node_db]
type = NuDB
path = /var/lib/xrpld/db/nudb

[database_path]
/var/lib/xrpld/db

[debug_logfile]
/var/log/xrpld/debug.log

[node_size]
huge

[beta_rpc_api]
1

[rpc_startup]
{ "command": "log_level", "severity": "warning" }
"""


def start_standalone_node(
    container_name: str,
    rpc_port: int,
    cfg_dir: str,
    ledger_path: str,
) -> JsonRpcClient:
    """Start a standalone xrpld container and wait until it's ready.

    Returns a sync JsonRpcClient connected to the node.
    Raises pytest.fail if the node doesn't reach 'standalone' or 'full' state.
    """
    print(f"\n  Container: {container_name}")
    print(f"  To tear down: docker rm -f {container_name}")

    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "-p",
            f"{rpc_port}:5005",
            "-v",
            f"{cfg_dir}:/etc/opt/xrpld",
            "-v",
            f"{ledger_path}:/ledger.json:ro",
            XRPLD_IMAGE,
            "-a",
            "--ledgerfile",
            "/ledger.json",
        ],
        check=True,
        timeout=30,
    )

    client = JsonRpcClient(f"http://localhost:{rpc_port}")

    deadline = time.time() + STARTUP_TIMEOUT
    last_state = ""
    while time.time() < deadline:
        try:
            response = client.request(ServerInfo())
            last_state = response.result.get("info", {}).get("server_state", "")
            if last_state in ("standalone", "full"):
                print(f"  Node ready: {last_state}")
                return client
        except Exception:
            pass
        time.sleep(0.2)

    logs = subprocess.run(
        ["docker", "logs", "--tail=30", container_name],
        capture_output=True,
        text=True,
        check=False,
    )
    pytest.fail(
        f"Standalone node stuck in '{last_state}' after {STARTUP_TIMEOUT}s.\nLogs:\n{logs.stdout}\n{logs.stderr}"
    )


def stop_container(container_name: str) -> None:
    """Remove a Docker container by name."""
    subprocess.run(["docker", "rm", "-f", container_name], check=False, timeout=15)


def ledger_accept(client: JsonRpcClient) -> None:
    """Advance the ledger in standalone mode."""
    client.request(GenericRequest(method="ledger_accept"))


def submit_txn(rpc_url: str, sender_seed: str, txn, label: str) -> dict:
    """Sign, submit a transaction synchronously, return result dict."""

    async def _inner():
        async_client = AsyncJsonRpcClient(rpc_url)
        wallet = Wallet.from_seed(sender_seed)
        signed = await autofill_and_sign(txn, async_client, wallet)
        response = await submit(signed, async_client)
        preliminary = response.result.get("engine_result", "")
        tx_hash = response.result.get("tx_json", {}).get("hash", "") or signed.get_hash()
        return {"hash": tx_hash, "preliminary": preliminary}

    result = asyncio.run(_inner())
    print(f"  {label}: {result['preliminary']}  hash={result['hash'][:16]}...")
    return result


def wait_for_tx(client: JsonRpcClient, tx_hash: str, label: str, timeout: int = 30):
    """Close ledgers until the transaction validates."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        ledger_accept(client)
        try:
            resp = client.request(Tx(transaction=tx_hash))
            meta = resp.result.get("meta", {})
            code = meta.get("TransactionResult")
            if code == "tesSUCCESS":
                print(f"  {label}: validated (tesSUCCESS)")
                return resp.result
            if code is not None and code != "tesSUCCESS":
                pytest.fail(f"{label} failed on-ledger: {code}")
        except Exception:
            pass
        time.sleep(0.5)
    pytest.fail(f"{label}: not validated after {timeout}s")


def get_trustline_balance(client: JsonRpcClient, address: str, currency: str, peer: str) -> str:
    """Get trustline balance for a specific currency/peer via account_lines."""
    response = client.request(AccountLines(account=address, peer=peer))
    for line in response.result.get("lines", []):
        if line["currency"] == currency:
            return line["balance"]
    return "0"


def fund_and_verify(client, rpc_url, gateway_addr, gateway_seed, trader_addr, currency, amount, label):
    """Fund a trader with tokens from the gateway and verify the balance."""
    fund_txn = Payment(
        account=gateway_addr,
        destination=trader_addr,
        amount=IssuedCurrencyAmount(currency=currency, issuer=gateway_addr, value=amount),
    )
    result = submit_txn(rpc_url, gateway_seed, fund_txn, f"Fund {label}")
    assert result["preliminary"] in ("tesSUCCESS", "terQUEUED"), f"Fund {label} rejected: {result}"
    wait_for_tx(client, result["hash"], f"Fund {label}")

    balance = get_trustline_balance(client, trader_addr, currency, gateway_addr)
    print(f"  {label} {currency} balance: {balance}")
    assert float(balance) > 0, f"{label} should have {currency} after funding, got {balance}"
    return balance
