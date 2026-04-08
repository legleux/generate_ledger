"""Smoke test: AMM crosses offers on the CLOB.

Proves that AMM pools integrated with the central limit order book (CLOB)
directly fill OfferCreate transactions. When a trader places an offer, the
matching engine checks both the orderbook and AMM pools for the best rate.

Setup:
  - 1 gateway issuing USD, BTC, CNY, ETH
  - Alice (trader) with trustlines for all 4 currencies
  - Bob (trader) with trustlines for all 4 currencies
  - AMM pool: USD/BTC (issued/issued, 10k each, 1% fee)
  - AMM pool: CNY/ETH (issued/issued, 10k each, 1% fee)

Flow:
  1. Gateway funds Alice with 1,000 USD, Bob with 1,000 CNY
  2. Alice submits OfferCreate: sell USD for BTC -- AMM pool crosses it
  3. Bob submits OfferCreate: sell CNY for ETH -- AMM pool crosses it
  4. Verify Alice received BTC and Bob received ETH

Uses a single xrpld node in standalone mode (no consensus needed).

Requires Docker. Skipped by default -- run with:
    pytest tests/smoke/test_amm_autobridge.py -m smoke --no-cov -v -s
"""

import asyncio
import json
import os
import subprocess
import time
import uuid

import pytest
from xrpl.asyncio.clients import AsyncJsonRpcClient
from xrpl.asyncio.transaction import autofill_and_sign, submit
from xrpl.clients import JsonRpcClient
from xrpl.models import IssuedCurrencyAmount, OfferCreate, OfferCreateFlag, Payment
from xrpl.models.requests import AccountLines, GenericRequest, ServerInfo, Tx
from xrpl.wallet import Wallet

pytestmark = pytest.mark.smoke

RPC_PORT = 5006
STARTUP_TIMEOUT = 30
KEEP_NETWORK = os.environ.get("SMOKE_KEEP_NETWORK", "0") == "1"
XRPLD_IMAGE = "rippleci/xrpld:develop"

# Issued/issued AMM pools -- no XRP, direct token pairs
# Format: currency1:issuer1:currency2:issuer2:amount1:amount2:fee
AMM_POOL_USD_BTC = "USD:0:BTC:0:10000:10000:100"
AMM_POOL_CNY_ETH = "CNY:0:ETH:0:10000:10000:100"

# Minimal xrpld.cfg for standalone mode
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


@pytest.fixture(scope="module")
def testnet_dir(tmp_path_factory):
    """Generate a ledger with 1 gateway, 2 traders, and 2 issued/issued AMM pools."""
    output_dir = tmp_path_factory.mktemp("smoke_amm")

    subprocess.run(
        [
            "uv",
            "run",
            "gen",
            "ledger",
            "--accounts",
            "2",
            "--gateways",
            "1",
            "--gateway-currencies",
            "USD,BTC,CNY,ETH",
            "--assets-per-gateway",
            "4",
            "--gateway-coverage",
            "1.0",
            "--gateway-connectivity",
            "1.0",
            "--amm-pool",
            AMM_POOL_USD_BTC,
            "--amm-pool",
            AMM_POOL_CNY_ETH,
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        timeout=30,
    )

    assert (output_dir / "ledger.json").exists()
    assert (output_dir / "accounts.json").exists()

    # Write standalone xrpld.cfg
    cfg_dir = output_dir / "xrpld"
    cfg_dir.mkdir()
    (cfg_dir / "xrpld.cfg").write_text(STANDALONE_CFG)

    return output_dir


@pytest.fixture(scope="module")
def accounts(testnet_dir):
    """Load accounts: index 0 = gateway, index 1 = Alice, index 2 = Bob."""
    data = json.loads((testnet_dir / "accounts.json").read_text())
    return [(addr, seed) for addr, seed in data]


@pytest.fixture(scope="module")
def container_name():
    """Unique container name to avoid conflicts with other test runs."""
    return f"smoke_amm_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def network(testnet_dir, container_name):
    """Start a single xrpld node in standalone mode, yield sync client."""
    ledger_path = str(testnet_dir / "ledger.json")
    cfg_dir = str(testnet_dir / "xrpld")

    print(f"\n  Testnet dir: {testnet_dir}")
    print(f"  Container: {container_name}")
    print(f"  To tear down: docker rm -f {container_name}")

    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "-p",
            f"{RPC_PORT}:5005",
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

    client = JsonRpcClient(f"http://localhost:{RPC_PORT}")

    # Wait for standalone node to be ready
    print("  Waiting for standalone node...")
    deadline = time.time() + STARTUP_TIMEOUT
    last_state = ""
    while time.time() < deadline:
        try:
            response = client.request(ServerInfo())
            last_state = response.result.get("info", {}).get("server_state", "")
            if last_state in ("standalone", "full"):
                print(f"  Node ready: {last_state}")
                break
        except Exception:
            pass
        time.sleep(1)
    else:
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

    yield client

    if KEEP_NETWORK:
        print("\n  SMOKE_KEEP_NETWORK=1: leaving container running.")
        print(f"  Container: {container_name}")
        print(f"  To tear down: docker rm -f {container_name}")
    else:
        subprocess.run(["docker", "rm", "-f", container_name], check=False, timeout=15)


def _ledger_accept(client: JsonRpcClient):
    """Advance the ledger in standalone mode."""
    client.request(GenericRequest(method="ledger_accept"))


def _get_trustline_balance(client: JsonRpcClient, address: str, currency: str, peer: str) -> str:
    """Get trustline balance for a specific currency/peer via account_lines."""
    response = client.request(AccountLines(account=address, peer=peer))
    for line in response.result.get("lines", []):
        if line["currency"] == currency:
            return line["balance"]
    return "0"


def _submit_txn(rpc_url: str, sender_seed: str, txn, label: str) -> dict:
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


def _wait_for_tx(client: JsonRpcClient, tx_hash: str, label: str, timeout: int = 30):
    """Close ledgers until the transaction validates."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        _ledger_accept(client)
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


def _fund_and_verify(client, rpc_url, gateway_addr, gateway_seed, trader_addr, currency, amount, label):
    """Fund a trader with tokens from the gateway and verify the balance."""
    fund_txn = Payment(
        account=gateway_addr,
        destination=trader_addr,
        amount=IssuedCurrencyAmount(currency=currency, issuer=gateway_addr, value=amount),
    )
    result = _submit_txn(rpc_url, gateway_seed, fund_txn, f"Fund {label}")
    assert result["preliminary"] in ("tesSUCCESS", "terQUEUED"), f"Fund {label} rejected: {result}"
    _wait_for_tx(client, result["hash"], f"Fund {label}")

    balance = _get_trustline_balance(client, trader_addr, currency, gateway_addr)
    print(f"  {label} {currency} balance: {balance}")
    assert float(balance) > 0, f"{label} should have {currency} after funding, got {balance}"
    return balance


def _offer_and_verify(client, rpc_url, trader_seed, trader_addr, gateway_addr, sell_currency, buy_currency, label):
    """Submit an OfferCreate and verify the trader received the buy currency."""
    offer_txn = OfferCreate(
        account=trader_addr,
        taker_gets=IssuedCurrencyAmount(currency=sell_currency, issuer=gateway_addr, value="100"),
        taker_pays=IssuedCurrencyAmount(currency=buy_currency, issuer=gateway_addr, value="50"),
        flags=OfferCreateFlag.TF_SELL,
    )
    result = _submit_txn(rpc_url, trader_seed, offer_txn, f"{label} Offer")
    assert result["preliminary"] in ("tesSUCCESS", "terQUEUED"), f"{label} offer rejected: {result}"
    _wait_for_tx(client, result["hash"], f"{label} Offer")

    sell_bal = _get_trustline_balance(client, trader_addr, sell_currency, gateway_addr)
    buy_bal = _get_trustline_balance(client, trader_addr, buy_currency, gateway_addr)
    return sell_bal, buy_bal


def test_amm_crosses_offers(accounts, network):
    """AMM pools directly cross Alice's and Bob's offers on the CLOB."""
    client = network
    rpc_url = f"http://localhost:{RPC_PORT}"

    assert len(accounts) >= 3, f"Expected 3 accounts (gateway + Alice + Bob), got {len(accounts)}"
    gateway_addr, gateway_seed = accounts[0]
    alice_addr, alice_seed = accounts[1]
    bob_addr, bob_seed = accounts[2]

    print(f"\nGateway: {gateway_addr}")
    print(f"Alice:   {alice_addr}")
    print(f"Bob:     {bob_addr}")

    # -- Phase 1: Fund traders --
    print("\n=== Phase 1: Funding traders ===")
    alice_usd = _fund_and_verify(client, rpc_url, gateway_addr, gateway_seed, alice_addr, "USD", "1000", "Alice")
    bob_cny = _fund_and_verify(client, rpc_url, gateway_addr, gateway_seed, bob_addr, "CNY", "1000", "Bob")

    # -- Phase 2: Offers -- AMM pools cross them directly --
    print("\n=== Phase 2: Alice sells USD for BTC, Bob sells CNY for ETH ===")

    alice_usd_after, alice_btc = _offer_and_verify(
        client,
        rpc_url,
        alice_seed,
        alice_addr,
        gateway_addr,
        "USD",
        "BTC",
        "Alice",
    )
    bob_cny_after, bob_eth = _offer_and_verify(
        client,
        rpc_url,
        bob_seed,
        bob_addr,
        gateway_addr,
        "CNY",
        "ETH",
        "Bob",
    )

    # -- Phase 3: Verify --
    print("\n=== Phase 3: Results ===")
    print(f"  Alice: USD {alice_usd} -> {alice_usd_after}, BTC 0 -> {alice_btc}")
    print(f"  Bob:   CNY {bob_cny} -> {bob_cny_after}, ETH 0 -> {bob_eth}")

    assert float(alice_btc) > 0, f"Alice should have BTC after offer, got {alice_btc}"
    assert float(alice_usd_after) < float(alice_usd), (
        f"Alice USD should have decreased: {alice_usd} -> {alice_usd_after}"
    )
    assert float(bob_eth) > 0, f"Bob should have ETH after offer, got {bob_eth}"
    assert float(bob_cny_after) < float(bob_cny), f"Bob CNY should have decreased: {bob_cny} -> {bob_cny_after}"

    alice_spent = float(alice_usd) - float(alice_usd_after)
    bob_spent = float(bob_cny) - float(bob_cny_after)
    print(f"\n  Alice: spent {alice_spent:.2f} USD, got {float(alice_btc):.2f} BTC")
    print(f"  Bob:   spent {bob_spent:.2f} CNY, got {float(bob_eth):.2f} ETH")

    print("\n=== AMM CLOB SMOKE TEST PASSED ===")
