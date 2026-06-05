"""Shared helpers for smoke tests.

Smoke tests previously duplicated standalone-node startup, transaction
submission, on-ledger polling, and balance lookups across files. This
module centralizes those primitives so individual test files can stay
focused on the scenario under test.

Not all helpers apply to every test: standalone-mode helpers
(STANDALONE_CFG, start_standalone_node) are for single-instance tests;
test_payment_ring.py runs a docker-compose multi-validator network and
only imports the transaction-submission helpers.
"""

import asyncio
import json
import os
import subprocess
import time
from pathlib import Path

import pytest
from xrpl.asyncio.clients import AsyncJsonRpcClient
from xrpl.asyncio.transaction import autofill_and_sign, submit
from xrpl.clients import JsonRpcClient
from xrpl.models.currencies import XRP, IssuedCurrency
from xrpl.models.requests import AccountLines, AMMInfo, GenericRequest, ServerInfo, Tx
from xrpl.wallet import Wallet

RPC_PORT_DEFAULT = 5006
XRPLD_IMAGE = "rippleci/xrpld:develop"
STARTUP_TIMEOUT = 30
KEEP_NETWORK = os.environ.get("SMOKE_KEEP_NETWORK", "0") == "1"

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


def write_standalone_cfg(cfg_dir: Path) -> None:
    """Materialize STANDALONE_CFG at cfg_dir/xrpld.cfg, creating cfg_dir if needed."""
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "xrpld.cfg").write_text(STANDALONE_CFG)


def load_accounts(testnet_dir: Path) -> list[tuple[str, str]]:
    """Read accounts.json and return [(address, seed), ...]."""
    data = json.loads((testnet_dir / "accounts.json").read_text())
    return [(addr, seed) for addr, seed in data]


def start_standalone_node(
    *,
    container_name: str,
    ledger_path: Path,
    cfg_dir: Path,
    rpc_port: int = RPC_PORT_DEFAULT,
) -> JsonRpcClient:
    """Start a single xrpld node in standalone mode and return a ready client.

    Raises pytest.fail on timeout, with `docker logs` tail attached.
    Caller is responsible for teardown (use teardown_node()).
    """
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
            "xrpld",
            "-a",
            "--ledgerfile",
            "/ledger.json",
        ],
        check=True,
        timeout=30,
    )

    client = JsonRpcClient(f"http://localhost:{rpc_port}")

    print("  Waiting for standalone node...")
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
        time.sleep(1)

    logs = subprocess.run(
        ["docker", "logs", "--tail=30", container_name],
        capture_output=True,
        text=True,
        check=False,
    )
    if not KEEP_NETWORK:
        subprocess.run(["docker", "rm", "-f", container_name], check=False, timeout=15)
    pytest.fail(
        f"Standalone node stuck in '{last_state}' after {STARTUP_TIMEOUT}s.\nLogs:\n{logs.stdout}\n{logs.stderr}"
    )


def teardown_node(container_name: str) -> None:
    """Remove the standalone container unless SMOKE_KEEP_NETWORK=1.

    Prints teardown instructions when keeping the container so the user
    can clean up manually.
    """
    if KEEP_NETWORK:
        print("\n  SMOKE_KEEP_NETWORK=1: leaving container running.")
        print(f"  Container: {container_name}")
        print(f"  To tear down: docker rm -f {container_name}")
    else:
        subprocess.run(["docker", "rm", "-f", container_name], check=False, timeout=15)


def ledger_accept(client: JsonRpcClient) -> None:
    """Advance the ledger in standalone mode."""
    client.request(GenericRequest(method="ledger_accept"))


def submit_txn(rpc_url: str, sender_seed: str, txn, label: str) -> dict:
    """Sign and submit a transaction synchronously. Returns {hash, preliminary}.

    Acceptable preliminary results are `tesSUCCESS` and `terQUEUED`
    (queued under async load). Use wait_for_tx() to confirm on-ledger.
    """

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


def wait_for_tx(client: JsonRpcClient, tx_hash: str, label: str, timeout: int = 30) -> dict:
    """Close ledgers in standalone mode until the transaction validates.

    Fails the test on non-tesSUCCESS result codes or on timeout.
    """
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
    """Return the trustline balance for `currency` between `address` and `peer`, or "0" if absent."""
    response = client.request(AccountLines(account=address, peer=peer))
    for line in response.result.get("lines", []):
        if line["currency"] == currency:
            return line["balance"]
    return "0"


def get_lp_balance(client: JsonRpcClient, holder: str, amm_account: str) -> str:
    """Return the LP token balance held by `holder` against the AMM pseudo-account.

    The LP token currency is a 40-hex value (0x03 + 19 bytes); this finds
    the single trustline whose peer is the AMM account.
    """
    response = client.request(AccountLines(account=holder, peer=amm_account))
    lines = response.result.get("lines", [])
    if not lines:
        return "0"
    # In a well-formed AMM there's exactly one LP trustline between holder and AMM.
    return lines[0]["balance"]


def _to_currency(currency: str | None, issuer: str | None):
    """Build an xrpl-py Currency model for AMMInfo queries.

    None/None -> XRP; otherwise IssuedCurrency.
    """
    if currency is None and issuer is None:
        return XRP()
    return IssuedCurrency(currency=currency, issuer=issuer)


def get_amm_state(
    client: JsonRpcClient,
    asset1_currency: str | None,
    asset1_issuer: str | None,
    asset2_currency: str | None,
    asset2_issuer: str | None,
) -> dict:
    """Fetch AMM state via amm_info RPC.

    Returns a dict with: amm_account, lp_token_balance (str), amount, amount2,
    trading_fee, plus the raw response under "raw".
    """
    asset = _to_currency(asset1_currency, asset1_issuer)
    asset2 = _to_currency(asset2_currency, asset2_issuer)
    response = client.request(AMMInfo(asset=asset, asset2=asset2))
    amm = response.result.get("amm", {})
    lpt = amm.get("lp_token", {})
    return {
        "amm_account": amm.get("account"),
        "lp_token_balance": lpt.get("value", "0"),
        "lp_token_currency": lpt.get("currency"),
        "lp_token_issuer": lpt.get("issuer"),
        "amount": amm.get("amount"),
        "amount2": amm.get("amount2"),
        "trading_fee": amm.get("trading_fee"),
        "raw": response.result,
    }
