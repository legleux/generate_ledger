"""Smoke test: AMMDeposit and AMMWithdraw against a genesis-created AMM.

The existing AMM smoke test (test_amm_autobridge.py) only exercises the pool
*passively* -- an OfferCreate gets autobridged through the AMM. This test
mutates the AMM's own state directly to verify:

  - The hardcoded OwnerCount on the AMM pseudo-account (amm.py:225) holds up
    when xrpld is forced to mutate the AMM's owner directory
  - The AMM <-> issuer trustline balance-sign convention (amm.py:317) is
    correct in both deposit and withdraw directions
  - LP token issuance against a genesis-created AMM works for a non-creator
    depositor (creating a new LP trustline from scratch) and on withdraw
    (burning LP tokens from an existing creator's trustline)

Setup:
  - 1 gateway issuing USD
  - Alice (account 1) is the AMM creator -- pre-populated with LP tokens
    by the genesis builder (amm.py:288-294)
  - Bob (account 2) is a non-creator depositor -- has a genesis USD
    trustline to the gateway (--gateway-coverage 1.0)
  - AMM pool: XRP (10,000) / USD (1,000), 0.5% fee, creator=Alice

Two tests share the module-scoped standalone network. They run sequentially;
each snapshots pre-state at entry and asserts deltas, so the second test
handles state mutated by the first.

Requires Docker. Skipped by default -- run with:
    pytest tests/smoke/test_amm_deposit_withdraw.py -m smoke --no-cov -v -s
"""

import subprocess
from decimal import Decimal

import pytest
from xrpl.models import AMMDeposit, AMMWithdraw, IssuedCurrencyAmount, Payment
from xrpl.models.requests import AccountInfo
from xrpl.models.transactions.amm_deposit import AMMDepositFlag
from xrpl.models.transactions.amm_withdraw import AMMWithdrawFlag

from tests.smoke._helpers import (
    RPC_PORT_DEFAULT,
    get_amm_state,
    get_lp_balance,
    get_trustline_balance,
    start_standalone_node,
    submit_txn,
    teardown_node,
    wait_for_tx,
    write_standalone_cfg,
)

pytestmark = pytest.mark.smoke

# XRP/USD AMM: 10,000 XRP (10 billion drops) and 1,000 USD, 0.5% fee, creator=account 1 (Alice)
AMM_POOL_XRP_USD = "XRP:USD:0:10000000000:1000:500:1"


@pytest.fixture(scope="module")
def testnet_dir(tmp_path_factory):
    """Generate a ledger with 1 gateway, Alice (AMM creator), Bob (depositor), and one XRP/USD AMM."""
    output_dir = tmp_path_factory.mktemp("smoke_amm_dw")

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
            "USD",
            "--assets-per-gateway",
            "1",
            "--gateway-coverage",
            "1.0",
            "--gateway-connectivity",
            "1.0",
            "--amm-pool",
            AMM_POOL_XRP_USD,
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        timeout=30,
    )

    assert (output_dir / "ledger.json").exists()
    assert (output_dir / "accounts.json").exists()

    write_standalone_cfg(output_dir / "xrpld")

    return output_dir


@pytest.fixture(scope="module")
def network(testnet_dir, container_name):
    """Start a single xrpld node in standalone mode."""
    print(f"\n  Testnet dir: {testnet_dir}")
    print(f"  Container: {container_name}")
    print(f"  To tear down: docker rm -f {container_name}")

    client = start_standalone_node(
        container_name=container_name,
        ledger_path=testnet_dir / "ledger.json",
        cfg_dir=testnet_dir / "xrpld",
        rpc_port=RPC_PORT_DEFAULT,
    )

    yield client

    teardown_node(container_name)


def _xrp_balance(client, address: str) -> int:
    """Account XRP balance in drops via account_info."""
    response = client.request(AccountInfo(account=address))
    return int(response.result["account_data"]["Balance"])


def _amm_owner_count(client, amm_account: str) -> int:
    """OwnerCount as xrpld currently sees it on the AMM pseudo-account."""
    response = client.request(AccountInfo(account=amm_account))
    return int(response.result["account_data"]["OwnerCount"])


def _snapshot(client, *, gateway_addr: str, alice_addr: str, bob_addr: str) -> dict:
    """Capture the AMM + participant state we'll be asserting against."""
    amm = get_amm_state(client, None, None, "USD", gateway_addr)
    amm_account = amm["amm_account"]
    snap = {
        "amm": amm,
        "amm_account": amm_account,
        "amm_xrp": _xrp_balance(client, amm_account),
        "amm_usd": get_trustline_balance(client, amm_account, "USD", gateway_addr),
        "amm_owner_count": _amm_owner_count(client, amm_account),
        "alice_xrp": _xrp_balance(client, alice_addr),
        "alice_usd": get_trustline_balance(client, alice_addr, "USD", gateway_addr),
        "alice_lp": get_lp_balance(client, alice_addr, amm_account),
        "bob_xrp": _xrp_balance(client, bob_addr),
        "bob_usd": get_trustline_balance(client, bob_addr, "USD", gateway_addr),
        "bob_lp": get_lp_balance(client, bob_addr, amm_account),
    }
    return snap


def _print_snap(label: str, snap: dict) -> None:
    print(f"\n  {label}:")
    print(f"    AMM account:        {snap['amm_account']}")
    print(f"    AMM XRP (drops):    {snap['amm_xrp']:,}")
    print(f"    AMM USD trustline:  {snap['amm_usd']}")
    print(f"    AMM LP outstanding: {snap['amm']['lp_token_balance']}")
    print(f"    AMM OwnerCount:     {snap['amm_owner_count']}")
    print(f"    Alice XRP:          {snap['alice_xrp']:,}  USD: {snap['alice_usd']}  LP: {snap['alice_lp']}")
    print(f"    Bob   XRP:          {snap['bob_xrp']:,}  USD: {snap['bob_usd']}  LP: {snap['bob_lp']}")


def test_amm_two_asset_deposit_then_withdraw(accounts, network):
    """Bob does a two-asset deposit; Alice does a proportional LP-token withdraw."""
    client = network
    rpc_url = f"http://localhost:{RPC_PORT_DEFAULT}"

    assert len(accounts) >= 3, f"Expected 3 accounts (gateway + Alice + Bob), got {len(accounts)}"
    gateway_addr, gateway_seed = accounts[0]
    alice_addr, _alice_seed = accounts[1]
    bob_addr, bob_seed = accounts[2]

    print(f"\nGateway: {gateway_addr}")
    print(f"Alice (creator): {alice_addr}")
    print(f"Bob (depositor): {bob_addr}")

    pre = _snapshot(client, gateway_addr=gateway_addr, alice_addr=alice_addr, bob_addr=bob_addr)
    _print_snap("Pre-state", pre)
    amm_account = pre["amm_account"]
    assert amm_account, "amm_info did not return an AMM account -- is the AMM in the genesis ledger?"

    # -- Phase 1: Fund Bob with 500 USD from the gateway --
    print("\n=== Phase 1: Gateway -> Bob 500 USD ===")
    fund_txn = Payment(
        account=gateway_addr,
        destination=bob_addr,
        amount=IssuedCurrencyAmount(currency="USD", issuer=gateway_addr, value="500"),
    )
    fund_result = submit_txn(rpc_url, gateway_seed, fund_txn, "Fund Bob USD")
    assert fund_result["preliminary"] in ("tesSUCCESS", "terQUEUED"), f"Fund rejected: {fund_result}"
    wait_for_tx(client, fund_result["hash"], "Fund Bob USD")
    bob_usd_after_fund = get_trustline_balance(client, bob_addr, "USD", gateway_addr)
    assert Decimal(bob_usd_after_fund) >= Decimal("500"), f"Bob USD should be >= 500, got {bob_usd_after_fund}"

    # -- Phase 2: Bob deposits 1000 XRP + 100 USD --
    print("\n=== Phase 2: Bob AMMDeposit (TF_TWO_ASSET) ===")
    deposit_xrp_drops = "1000000000"  # 1000 XRP in drops
    deposit_usd = "100"
    deposit_txn = AMMDeposit(
        account=bob_addr,
        asset={"currency": "XRP"},
        asset2={"currency": "USD", "issuer": gateway_addr},
        amount=deposit_xrp_drops,
        amount2=IssuedCurrencyAmount(currency="USD", issuer=gateway_addr, value=deposit_usd),
        flags=AMMDepositFlag.TF_TWO_ASSET,
    )
    deposit_result = submit_txn(rpc_url, bob_seed, deposit_txn, "Bob AMMDeposit")
    assert deposit_result["preliminary"] in ("tesSUCCESS", "terQUEUED"), f"Deposit rejected: {deposit_result}"
    wait_for_tx(client, deposit_result["hash"], "Bob AMMDeposit")

    post_deposit = _snapshot(client, gateway_addr=gateway_addr, alice_addr=alice_addr, bob_addr=bob_addr)
    _print_snap("Post-deposit", post_deposit)

    # Deltas
    assert Decimal(post_deposit["bob_lp"]) > Decimal("0"), "Bob should hold LP tokens after deposit"
    assert Decimal(post_deposit["amm"]["lp_token_balance"]) > Decimal(pre["amm"]["lp_token_balance"]), (
        "AMM total LP outstanding should increase"
    )
    assert post_deposit["amm_xrp"] >= pre["amm_xrp"] + int(deposit_xrp_drops) - 1000, (
        f"AMM XRP should increase by ~{deposit_xrp_drops} drops"
    )
    assert Decimal(post_deposit["amm_usd"]) > Decimal(pre["amm_usd"]), "AMM USD trustline should increase"
    assert Decimal(post_deposit["bob_usd"]) < Decimal(bob_usd_after_fund), "Bob USD should decrease"
    # The OwnerCount question: capture whatever xrpld now reports. We don't pin
    # an exact value -- this is the diagnostic measurement that informs whether
    # our hardcoded `OwnerCount: 1` in amm.py:225 matches xrpld's view.
    assert isinstance(post_deposit["amm_owner_count"], int) and post_deposit["amm_owner_count"] >= 1, (
        f"AMM OwnerCount should be a positive int, got {post_deposit['amm_owner_count']!r}"
    )
    print(f"  >>> AMM OwnerCount after deposit: {post_deposit['amm_owner_count']} (genesis hardcoded as 1)")

    # -- Phase 3: Alice burns 10% of her LP tokens --
    print("\n=== Phase 3: Alice AMMWithdraw (TF_LP_TOKEN, ~10% of her LP) ===")
    alice_lp_pre = Decimal(pre["alice_lp"])  # snapshot from before any deposit
    burn_lp = (alice_lp_pre / Decimal(10)).quantize(Decimal("0.000001"))
    lp_currency = post_deposit["amm"]["lp_token_currency"]
    lp_issuer = post_deposit["amm"]["lp_token_issuer"]
    assert lp_currency and lp_issuer, "amm_info should return lp_token currency + issuer"

    withdraw_txn = AMMWithdraw(
        account=alice_addr,
        asset={"currency": "XRP"},
        asset2={"currency": "USD", "issuer": gateway_addr},
        lp_token_in=IssuedCurrencyAmount(currency=lp_currency, issuer=lp_issuer, value=str(burn_lp)),
        flags=AMMWithdrawFlag.TF_LP_TOKEN,
    )
    withdraw_result = submit_txn(rpc_url, accounts[1][1], withdraw_txn, "Alice AMMWithdraw")
    assert withdraw_result["preliminary"] in ("tesSUCCESS", "terQUEUED"), f"Withdraw rejected: {withdraw_result}"
    wait_for_tx(client, withdraw_result["hash"], "Alice AMMWithdraw")

    post_withdraw = _snapshot(client, gateway_addr=gateway_addr, alice_addr=alice_addr, bob_addr=bob_addr)
    _print_snap("Post-withdraw", post_withdraw)

    # Alice's LP balance dropped by exactly burn_lp
    delta_alice_lp = Decimal(post_deposit["alice_lp"]) - Decimal(post_withdraw["alice_lp"])
    assert delta_alice_lp == burn_lp, f"Alice LP delta {delta_alice_lp} != burned {burn_lp}"
    # AMM total LP decreased
    assert Decimal(post_withdraw["amm"]["lp_token_balance"]) < Decimal(post_deposit["amm"]["lp_token_balance"]), (
        "AMM LP outstanding should decrease after withdraw"
    )
    # AMM XRP and USD decreased
    assert post_withdraw["amm_xrp"] < post_deposit["amm_xrp"], "AMM XRP should decrease after withdraw"
    assert Decimal(post_withdraw["amm_usd"]) < Decimal(post_deposit["amm_usd"]), (
        "AMM USD trustline should decrease after withdraw"
    )
    # Alice received both assets back (her USD goes up, XRP goes up modulo tx fee)
    assert Decimal(post_withdraw["alice_usd"]) > Decimal(pre["alice_usd"]), "Alice USD should increase after withdraw"
    # Alice XRP: net delta could be small (tx fee ~10 drops vs returned XRP) -- assert it didn't crater
    assert post_withdraw["alice_xrp"] >= pre["alice_xrp"] - 100, "Alice XRP shouldn't drop more than a tx-fee's worth"

    print("\n=== TWO-ASSET DEPOSIT + LP-TOKEN WITHDRAW PASSED ===")


def test_amm_single_asset_deposit_then_withdraw(accounts, network):
    """Bob does a single-asset XRP deposit, then a single-asset XRP withdraw.

    Runs after test_amm_two_asset_deposit_then_withdraw (pytest collects in
    source order within a file). Operates on the post-test-1 pool state.
    """
    client = network
    rpc_url = f"http://localhost:{RPC_PORT_DEFAULT}"

    gateway_addr, _gateway_seed = accounts[0]
    alice_addr, _alice_seed = accounts[1]
    bob_addr, bob_seed = accounts[2]

    pre = _snapshot(client, gateway_addr=gateway_addr, alice_addr=alice_addr, bob_addr=bob_addr)
    _print_snap("Pre-state (single-asset test)", pre)
    amm_account = pre["amm_account"]
    bob_lp_pre = Decimal(pre["bob_lp"])

    # -- Phase 1: Bob deposits 500 XRP only --
    print("\n=== Phase 1: Bob AMMDeposit (TF_SINGLE_ASSET, 500 XRP) ===")
    deposit_xrp_drops = "500000000"  # 500 XRP in drops
    deposit_txn = AMMDeposit(
        account=bob_addr,
        asset={"currency": "XRP"},
        asset2={"currency": "USD", "issuer": gateway_addr},
        amount=deposit_xrp_drops,
        flags=AMMDepositFlag.TF_SINGLE_ASSET,
    )
    deposit_result = submit_txn(rpc_url, bob_seed, deposit_txn, "Bob single-asset AMMDeposit")
    assert deposit_result["preliminary"] in ("tesSUCCESS", "terQUEUED"), f"Deposit rejected: {deposit_result}"
    wait_for_tx(client, deposit_result["hash"], "Bob single-asset AMMDeposit")

    post_deposit = _snapshot(client, gateway_addr=gateway_addr, alice_addr=alice_addr, bob_addr=bob_addr)
    _print_snap("Post-deposit", post_deposit)

    # Bob's LP increased
    assert Decimal(post_deposit["bob_lp"]) > bob_lp_pre, "Bob's LP should increase after single-asset deposit"
    # AMM total LP increased
    assert Decimal(post_deposit["amm"]["lp_token_balance"]) > Decimal(pre["amm"]["lp_token_balance"]), (
        "AMM LP outstanding should increase"
    )
    # AMM XRP increased by ~500 XRP
    assert post_deposit["amm_xrp"] >= pre["amm_xrp"] + int(deposit_xrp_drops) - 1000, (
        "AMM XRP should increase by ~500 XRP"
    )
    # USD side unchanged (single-asset deposit only touches one leg)
    assert Decimal(post_deposit["amm_usd"]) == Decimal(pre["amm_usd"]), (
        f"AMM USD trustline should not change on single-asset XRP deposit: "
        f"{pre['amm_usd']} -> {post_deposit['amm_usd']}"
    )
    # OwnerCount still consistent
    assert isinstance(post_deposit["amm_owner_count"], int) and post_deposit["amm_owner_count"] >= 1
    print(f"  >>> AMM OwnerCount after single-asset deposit: {post_deposit['amm_owner_count']}")

    # -- Phase 2: Bob withdraws ~50% of his LP for XRP only --
    print("\n=== Phase 2: Bob AMMWithdraw (TF_ONE_ASSET_LP_TOKEN, ~50% of his LP) ===")
    burn_lp = (Decimal(post_deposit["bob_lp"]) / Decimal(2)).quantize(Decimal("0.000001"))
    lp_currency = post_deposit["amm"]["lp_token_currency"]
    lp_issuer = post_deposit["amm"]["lp_token_issuer"]

    withdraw_txn = AMMWithdraw(
        account=bob_addr,
        asset={"currency": "XRP"},
        asset2={"currency": "USD", "issuer": gateway_addr},
        # Amount sets the floor / asset selector for one-asset withdraw; 1 drop is a no-op floor
        amount="1",
        lp_token_in=IssuedCurrencyAmount(currency=lp_currency, issuer=lp_issuer, value=str(burn_lp)),
        flags=AMMWithdrawFlag.TF_ONE_ASSET_LP_TOKEN,
    )
    withdraw_result = submit_txn(rpc_url, bob_seed, withdraw_txn, "Bob single-asset AMMWithdraw")
    assert withdraw_result["preliminary"] in ("tesSUCCESS", "terQUEUED"), f"Withdraw rejected: {withdraw_result}"
    wait_for_tx(client, withdraw_result["hash"], "Bob single-asset AMMWithdraw")

    post_withdraw = _snapshot(client, gateway_addr=gateway_addr, alice_addr=alice_addr, bob_addr=bob_addr)
    _print_snap("Post-withdraw", post_withdraw)

    # Bob's LP burned
    delta_bob_lp = Decimal(post_deposit["bob_lp"]) - Decimal(post_withdraw["bob_lp"])
    assert delta_bob_lp == burn_lp, f"Bob LP delta {delta_bob_lp} != burned {burn_lp}"
    # AMM XRP decreased
    assert post_withdraw["amm_xrp"] < post_deposit["amm_xrp"], "AMM XRP should decrease after single-asset withdraw"
    # AMM USD unchanged (we withdrew XRP only)
    assert Decimal(post_withdraw["amm_usd"]) == Decimal(post_deposit["amm_usd"]), (
        f"AMM USD should not change on one-asset XRP withdraw: {post_deposit['amm_usd']} -> {post_withdraw['amm_usd']}"
    )
    # Bob got XRP back
    assert post_withdraw["bob_xrp"] > post_deposit["bob_xrp"], "Bob XRP should increase after withdraw"

    print(f"  AMM account: {amm_account}")
    print("\n=== SINGLE-ASSET DEPOSIT + ONE-ASSET-LP-TOKEN WITHDRAW PASSED ===")
