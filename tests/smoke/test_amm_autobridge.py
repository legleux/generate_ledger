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

import subprocess

import pytest
from xrpl.models import IssuedCurrencyAmount, OfferCreate, OfferCreateFlag

from tests.smoke.helpers import (
    STANDALONE_CFG,
    fund_and_verify,
    get_trustline_balance,
    submit_txn,
    wait_for_tx,
)

pytestmark = pytest.mark.smoke

# Issued/issued AMM pools -- no XRP, direct token pairs
# Format: currency1:issuer1:currency2:issuer2:amount1:amount2:fee
AMM_POOL_USD_BTC = "USD:0:BTC:0:10000:10000:100"
AMM_POOL_CNY_ETH = "CNY:0:ETH:0:10000:10000:100"


@pytest.fixture(scope="module")
def rpc_port():
    return 5006


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

    cfg_dir = output_dir / "xrpld"
    cfg_dir.mkdir()
    (cfg_dir / "xrpld.cfg").write_text(STANDALONE_CFG)

    return output_dir


def _offer_and_verify(client, rpc_url, trader_seed, trader_addr, gateway_addr, sell_currency, buy_currency, label):
    """Submit an OfferCreate and verify the trader received the buy currency."""
    offer_txn = OfferCreate(
        account=trader_addr,
        taker_gets=IssuedCurrencyAmount(currency=sell_currency, issuer=gateway_addr, value="100"),
        taker_pays=IssuedCurrencyAmount(currency=buy_currency, issuer=gateway_addr, value="50"),
        flags=OfferCreateFlag.TF_SELL,
    )
    result = submit_txn(rpc_url, trader_seed, offer_txn, f"{label} Offer")
    assert result["preliminary"] in ("tesSUCCESS", "terQUEUED"), f"{label} offer rejected: {result}"
    wait_for_tx(client, result["hash"], f"{label} Offer")

    sell_bal = get_trustline_balance(client, trader_addr, sell_currency, gateway_addr)
    buy_bal = get_trustline_balance(client, trader_addr, buy_currency, gateway_addr)
    return sell_bal, buy_bal


def test_amm_crosses_offers(accounts, network, rpc_port):
    """AMM pools directly cross Alice's and Bob's offers on the CLOB."""
    client = network
    rpc_url = f"http://localhost:{rpc_port}"

    assert len(accounts) >= 3, f"Expected 3 accounts (gateway + Alice + Bob), got {len(accounts)}"
    gateway_addr, gateway_seed = accounts[0]
    alice_addr, alice_seed = accounts[1]
    bob_addr, bob_seed = accounts[2]

    print(f"\nGateway: {gateway_addr}")
    print(f"Alice:   {alice_addr}")
    print(f"Bob:     {bob_addr}")

    # -- Phase 1: Fund traders --
    print("\n=== Phase 1: Funding traders ===")
    alice_usd = fund_and_verify(client, rpc_url, gateway_addr, gateway_seed, alice_addr, "USD", "1000", "Alice")
    bob_cny = fund_and_verify(client, rpc_url, gateway_addr, gateway_seed, bob_addr, "CNY", "1000", "Bob")

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
