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
from xrpl.models import MPTokenAuthorize, Payment
from xrpl.models.amounts import MPTAmount
from xrpl.models.requests import AccountObjects, GenericRequest, ServerInfo, Tx
from xrpl.models.requests.account_objects import AccountObjectType
from xrpl.wallet import Wallet

pytestmark = pytest.mark.smoke

RPC_PORT = 5006
STARTUP_TIMEOUT = 30
KEEP_NETWORK = os.environ.get("SMOKE_KEEP_NETWORK", "0") == "1"
XRPLD_IMAGE = "rippleci/xrpld:develop"

# MPT issuance: issuer=account 0, sequence=1, max_amount=1M, flags=0x20 (lsfMPTCanTransfer)
MPT_SPEC = "0:1:1000000:32"

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
def accounts(testnet_dir):
    """Load accounts: 0=issuer, 1=alice, 2=bob."""
    data = json.loads((testnet_dir / "accounts.json").read_text())
    return [(addr, seed) for addr, seed in data]


@pytest.fixture(scope="module")
def mpt_issuance_id(accounts):
    """Compute the MPT issuance ID from issuer address and sequence."""
    from generate_ledger.indices import mpt_id_to_hex

    issuer_addr = accounts[0][0]
    return mpt_id_to_hex(1, issuer_addr)


@pytest.fixture(scope="module")
def container_name():
    return f"smoke_mpt_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def network(testnet_dir, container_name):
    """Start a single xrpld node in standalone mode."""
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


def _submit_txn(rpc_url: str, sender_seed: str, txn, label: str) -> dict:
    """Sign, submit a transaction, return result dict."""

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


def _get_mpt_balance(client: JsonRpcClient, address: str, mpt_id: str) -> int:
    """Get an account's MPT balance by querying its MPToken objects."""
    response = client.request(AccountObjects(account=address, type=AccountObjectType.MPTOKEN))
    for obj in response.result.get("account_objects", []):
        if obj.get("MPTokenIssuanceID") == mpt_id:
            return int(obj.get("MPTAmount", "0"))
    return 0


def test_mpt_transfer(accounts, network, mpt_issuance_id):
    """Authorize holders, fund Alice, transfer MPT from Alice to Bob."""
    client = network
    rpc_url = f"http://localhost:{RPC_PORT}"

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
        result = _submit_txn(rpc_url, seed, auth_txn, f"{name} authorize")
        assert result["preliminary"] in ("tesSUCCESS", "terQUEUED"), f"{name} authorize rejected: {result}"
        _wait_for_tx(client, result["hash"], f"{name} authorize")

    # -- Phase 2: Issuer funds Alice with 1,000 MPT --
    print("\n=== Phase 2: Issuer sends 1,000 MPT to Alice ===")
    fund_txn = Payment(
        account=issuer_addr,
        destination=alice_addr,
        amount=MPTAmount(mpt_issuance_id=mpt_id, value="1000"),
    )
    fund_result = _submit_txn(rpc_url, issuer_seed, fund_txn, "Fund Alice")
    assert fund_result["preliminary"] in ("tesSUCCESS", "terQUEUED"), f"Fund rejected: {fund_result}"
    _wait_for_tx(client, fund_result["hash"], "Fund Alice")

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
    transfer_result = _submit_txn(rpc_url, alice_seed, transfer_txn, "Alice -> Bob")
    assert transfer_result["preliminary"] in ("tesSUCCESS", "terQUEUED"), f"Transfer rejected: {transfer_result}"
    _wait_for_tx(client, transfer_result["hash"], "Alice -> Bob")

    # -- Phase 4: Verify final balances --
    print("\n=== Phase 4: Verify balances ===")
    alice_final = _get_mpt_balance(client, alice_addr, mpt_id)
    bob_final = _get_mpt_balance(client, bob_addr, mpt_id)
    print(f"  Alice: 1000 -> {alice_final}")
    print(f"  Bob:   0 -> {bob_final}")

    assert alice_final == 900, f"Alice should have 900 MPT, got {alice_final}"
    assert bob_final == 100, f"Bob should have 100 MPT, got {bob_final}"

    print("\n=== MPT TRANSFER SMOKE TEST PASSED ===")
