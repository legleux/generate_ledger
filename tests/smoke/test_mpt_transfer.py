"""Smoke test: MPT issuance, authorization, funding, and transfer.

Proves that an MPTokenIssuance baked into the genesis ledger is functional:
holders can authorize, the issuer can fund them, and holders can transfer
tokens to each other.

Setup:
  - 3 accounts: issuer (account 0), alice (account 1), bob (account 2)
  - 1 MPTokenIssuance (issuer=account 0, lsfMPTCanTransfer=0x20)

Flow:
  1. Alice and Bob send MPTokenAuthorize to opt in to the issuance
  2. Issuer sends 1,000 MPT to Alice via Payment
  3. Alice sends 100 MPT to Bob via Payment
  4. Verify: Alice has 900, Bob has 100

Uses a single xrpld node in standalone mode (no consensus needed).

Requires Docker. Skipped by default -- run with:
    pytest tests/smoke/test_mpt_transfer.py -m smoke --no-cov -v -s
"""

import subprocess

import pytest
from xrpl.clients import JsonRpcClient
from xrpl.models import MPTokenAuthorize, Payment
from xrpl.models.amounts import MPTAmount
from xrpl.models.requests import AccountObjects
from xrpl.models.requests.account_objects import AccountObjectType

from tests.smoke.helpers import STANDALONE_CFG, submit_txn, wait_for_tx

pytestmark = pytest.mark.smoke

# MPT issuance: issuer=account 0, sequence=1, max_amount=1M, flags=0x20 (lsfMPTCanTransfer)
MPT_SPEC = "0:1:1000000:32"


@pytest.fixture(scope="module")
def rpc_port():
    return 5007


@pytest.fixture(scope="module")
def testnet_dir(tmp_path_factory):
    """Generate a ledger with 3 accounts and 1 MPT issuance."""
    output_dir = tmp_path_factory.mktemp("smoke_mpt")

    subprocess.run(
        [
            "uv",
            "run",
            "gen",
            "ledger",
            "--accounts",
            "3",
            "--gateways",
            "0",
            "--mpt",
            MPT_SPEC,
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


@pytest.fixture(scope="module")
def mpt_issuance_id(accounts):
    """Compute the MPT issuance ID from issuer address and sequence."""
    from generate_ledger.indices import mpt_id_to_hex

    issuer_addr = accounts[0][0]
    return mpt_id_to_hex(1, issuer_addr)


def _get_mpt_balance(client: JsonRpcClient, address: str, mpt_id: str) -> int:
    """Get an account's MPT balance by querying its MPToken objects."""
    response = client.request(AccountObjects(account=address, type=AccountObjectType.MPTOKEN))
    for obj in response.result.get("account_objects", []):
        if obj.get("MPTokenIssuanceID") == mpt_id:
            return int(obj.get("MPTAmount", "0"))
    return 0


def test_mpt_transfer(accounts, network, mpt_issuance_id, rpc_port):
    """Authorize holders, fund Alice, transfer MPT from Alice to Bob."""
    client = network
    rpc_url = f"http://localhost:{rpc_port}"

    assert len(accounts) >= 3, f"Expected 3 accounts, got {len(accounts)}"
    issuer_addr, issuer_seed = accounts[0]
    alice_addr, alice_seed = accounts[1]
    bob_addr, bob_seed = accounts[2]
    mpt_id = mpt_issuance_id

    print(f"\nIssuer: {issuer_addr}")
    print(f"Alice:  {alice_addr}")
    print(f"Bob:    {bob_addr}")
    print(f"MPT ID: {mpt_id}")

    # -- Phase 1: Authorize holders --
    print("\n=== Phase 1: Alice and Bob authorize (opt in) ===")
    for name, addr, seed in [("Alice", alice_addr, alice_seed), ("Bob", bob_addr, bob_seed)]:
        auth_txn = MPTokenAuthorize(account=addr, mptoken_issuance_id=mpt_id)
        result = submit_txn(rpc_url, seed, auth_txn, f"{name} authorize")
        assert result["preliminary"] in ("tesSUCCESS", "terQUEUED"), f"{name} authorize rejected: {result}"
        wait_for_tx(client, result["hash"], f"{name} authorize")

    # -- Phase 2: Issuer funds Alice with 1,000 MPT --
    print("\n=== Phase 2: Issuer sends 1,000 MPT to Alice ===")
    fund_txn = Payment(
        account=issuer_addr,
        destination=alice_addr,
        amount=MPTAmount(mpt_issuance_id=mpt_id, value="1000"),
    )
    fund_result = submit_txn(rpc_url, issuer_seed, fund_txn, "Fund Alice")
    assert fund_result["preliminary"] in ("tesSUCCESS", "terQUEUED"), f"Fund rejected: {fund_result}"
    wait_for_tx(client, fund_result["hash"], "Fund Alice")

    alice_bal = _get_mpt_balance(client, alice_addr, mpt_id)
    print(f"  Alice MPT balance: {alice_bal}")
    assert alice_bal == 1000, f"Expected Alice to have 1000 MPT, got {alice_bal}"

    # -- Phase 3: Alice transfers 100 MPT to Bob --
    print("\n=== Phase 3: Alice sends 100 MPT to Bob ===")
    transfer_txn = Payment(
        account=alice_addr,
        destination=bob_addr,
        amount=MPTAmount(mpt_issuance_id=mpt_id, value="100"),
    )
    transfer_result = submit_txn(rpc_url, alice_seed, transfer_txn, "Alice -> Bob")
    assert transfer_result["preliminary"] in ("tesSUCCESS", "terQUEUED"), f"Transfer rejected: {transfer_result}"
    wait_for_tx(client, transfer_result["hash"], "Alice -> Bob")

    # -- Phase 4: Verify final balances --
    print("\n=== Phase 4: Verify balances ===")
    alice_final = _get_mpt_balance(client, alice_addr, mpt_id)
    bob_final = _get_mpt_balance(client, bob_addr, mpt_id)
    print(f"  Alice: 1000 -> {alice_final}")
    print(f"  Bob:   0 -> {bob_final}")

    assert alice_final == 900, f"Alice should have 900 MPT, got {alice_final}"
    assert bob_final == 100, f"Bob should have 100 MPT, got {bob_final}"

    print("\n=== MPT TRANSFER SMOKE TEST PASSED ===")
