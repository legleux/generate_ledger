"""Smoke test: generate a network, boot it, and send 100 Payment transactions.

Each of the 100 accounts sends 100 XRP to the next account in a ring
(account 99 sends to account 0). Payments are submitted in parallel since
each originates from a different account (independent sequence numbers).

After all payments settle, verify every account has the expected balance
and every transaction appears on-ledger.

Requires Docker and docker compose. Skipped by default — run with:
    pytest tests/smoke/ -m smoke --no-cov -v -s

Options:
    SMOKE_KEEP_NETWORK=1  — leave the network running after the test
"""

import asyncio
import subprocess
import time
import uuid

import pytest
from xrpl.asyncio.clients import AsyncJsonRpcClient
from xrpl.asyncio.transaction import autofill_and_sign, submit
from xrpl.clients import JsonRpcClient
from xrpl.models import Payment
from xrpl.models.requests import AccountInfo, Fee, ServerInfo, Tx
from xrpl.utils import xrp_to_drops
from xrpl.wallet import Wallet

from tests.smoke.conftest import KEEP_NETWORK

pytestmark = [pytest.mark.smoke, pytest.mark.network]

NUM_ACCOUNTS = 100
XRP_AMOUNT = 100
RPC_PORT = 5006  # Default mapped port for val0
NETWORK_TIMEOUT = 60  # Max seconds to wait for proposing


@pytest.fixture(scope="module")
def testnet_dir(tmp_path_factory):
    """Generate a complete testnet via the CLI with all defaults."""
    output_dir = tmp_path_factory.mktemp("smoke_testnet")

    subprocess.run(
        ["uv", "run", "gen", "--accounts", str(NUM_ACCOUNTS), "--gateways", "0", "--output-dir", str(output_dir)],
        check=True,
        timeout=30,
    )

    assert (output_dir / "ledger.json").exists()
    assert (output_dir / "accounts.json").exists()
    assert (output_dir / "docker-compose.yml").exists()

    return output_dir


@pytest.fixture(scope="module")
def compose_project():
    """Unique compose project name to avoid container name conflicts."""
    return f"smoke_ring_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def network(testnet_dir, compose_project):
    """Start the network with docker compose, wait for proposing, yield client."""
    compose_file = str(testnet_dir / "docker-compose.yml")
    compose_cmd = ["docker", "compose", "-f", compose_file, "-p", compose_project]

    print(f"\n  Testnet dir: {testnet_dir}")
    print(f"  Compose file: {compose_file}")
    print(f"  Project: {compose_project}")
    print(f"  To tear down: docker compose -f {compose_file} -p {compose_project} down -v")

    subprocess.run(
        [*compose_cmd, "up", "-d"],
        check=True,
        timeout=30,
    )

    client = JsonRpcClient(f"http://localhost:{RPC_PORT}")

    # Early health check: val0 should be syncing within ~10s
    print("\n  Waiting for val0 to start syncing...")
    time.sleep(10)
    try:
        response = client.request(ServerInfo())
        early_state = response.result.get("info", {}).get("server_state", "")
        print(f"  val0 state after 10s: {early_state}")
        if early_state not in ("syncing", "tracking", "full", "validating", "proposing"):
            logs = subprocess.run(
                [*compose_cmd, "logs", "--tail=20"],
                capture_output=True,
                text=True,
                check=False,
            )
            if not KEEP_NETWORK:
                subprocess.run([*compose_cmd, "down", "-v"], check=False, timeout=15)
            pytest.fail(
                f"val0 in unexpected state '{early_state}' after 10s (expected syncing or better).\n"
                f"Logs:\n{logs.stdout}"
            )
    except Exception as e:
        if not KEEP_NETWORK:
            subprocess.run([*compose_cmd, "down", "-v"], check=False, timeout=15)
        pytest.fail(f"Cannot reach val0 RPC after 10s: {e}")

    # Wait for proposing
    deadline = time.time() + NETWORK_TIMEOUT
    last_state = early_state
    while time.time() < deadline:
        try:
            response = client.request(ServerInfo())
            last_state = response.result.get("info", {}).get("server_state", "")
            if last_state == "proposing":
                print("  val0 reached 'proposing'")
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        logs = subprocess.run(
            [*compose_cmd, "logs", "--tail=30"],
            capture_output=True,
            text=True,
            check=False,
        )
        if not KEEP_NETWORK:
            subprocess.run([*compose_cmd, "down", "-v"], check=False, timeout=15)
        pytest.fail(
            f"Network stuck in '{last_state}' (not 'proposing') after {NETWORK_TIMEOUT}s.\nLogs:\n{logs.stdout}"
        )

    yield client

    if KEEP_NETWORK:
        print("\n  SMOKE_KEEP_NETWORK=1: leaving network running.")
        print(f"  Testnet dir: {testnet_dir}")
        print(f"  To tear down: docker compose -f {compose_file} -p {compose_project} down -v")
    else:
        subprocess.run([*compose_cmd, "down", "-v"], check=False, timeout=15)


def _get_balance(client: JsonRpcClient, address: str) -> int:
    """Get account balance in drops via account_info RPC."""
    response = client.request(AccountInfo(account=address))
    return int(response.result["account_data"]["Balance"])


async def _submit_payment(
    client: AsyncJsonRpcClient,
    sender_seed: str,
    sender_addr: str,
    receiver_addr: str,
    amount_drops: str,
) -> dict:
    """Sign, submit, and return preliminary result. Non-blocking."""
    wallet = Wallet.from_seed(sender_seed)
    payment = Payment(
        account=sender_addr,
        destination=receiver_addr,
        amount=amount_drops,
    )
    signed = await autofill_and_sign(payment, client, wallet)
    response = await submit(signed, client)
    preliminary = response.result.get("engine_result", "")
    tx_hash = response.result.get("tx_json", {}).get("hash", "") or signed.get_hash()
    return {
        "sender": sender_addr,
        "receiver": receiver_addr,
        "hash": tx_hash,
        "preliminary": preliminary,
    }


def test_payment_ring(accounts, network):
    """Verify genesis balances, submit payments in parallel, verify final balances."""
    client = network
    n = len(accounts)
    assert n == NUM_ACCOUNTS, f"Expected {NUM_ACCOUNTS} accounts, got {n}"

    rpc_url = f"http://localhost:{RPC_PORT}"
    send_drops = xrp_to_drops(XRP_AMOUNT)

    # Query the network fee before doing anything
    fee_response = client.request(Fee())
    base_fee = int(fee_response.result["drops"]["base_fee"])
    print(f"\nNetwork fee: {base_fee} drops")

    # -- Phase 1: Verify initial balances from genesis --
    print(f"\n=== Phase 1: Checking initial balances ({n} accounts) ===")
    initial_balances = {}
    for addr, _ in accounts:
        bal = _get_balance(client, addr)
        initial_balances[addr] = bal
        print(f"  {addr}  {bal:>15,} drops  ({bal / 1_000_000:,.0f} XRP)")
    balances_set = set(initial_balances.values())
    assert len(balances_set) == 1, f"Accounts have mixed initial balances: {balances_set}"
    initial_balance = balances_set.pop()
    print(f"  --- All {n} accounts: {initial_balance:,} drops ---")

    # -- Phase 2: Submit all payments concurrently (async) --
    print(f"\n=== Phase 2: Submitting {n} payments (async) ===")

    async def _submit_all():
        async_client = AsyncJsonRpcClient(rpc_url)
        tasks = []
        for i in range(n):
            sender_addr, sender_seed = accounts[i]
            receiver_addr, _ = accounts[(i + 1) % n]
            tasks.append(_submit_payment(async_client, sender_seed, sender_addr, receiver_addr, send_drops))
        return await asyncio.gather(*tasks, return_exceptions=True)

    raw_results = asyncio.run(_submit_all())

    results = []
    for i, r in enumerate(raw_results):
        if isinstance(r, Exception):
            results.append((i, {"sender": accounts[i][0], "error": str(r)}))
            print(f"  [{i:>3}] {accounts[i][0]} ERROR: {r}")
        else:
            results.append((i, r))
            print(f"  [{i:>3}] {r['sender']} → {r['receiver']}  {XRP_AMOUNT} XRP  {r['preliminary']}")

    # Check preliminary results — tesSUCCESS and terQUEUED are both valid
    # tesSUCCESS = applied to current open ledger
    # terQUEUED = queued for next ledger (normal under async load)
    accepted = {"tesSUCCESS", "terQUEUED"}
    rejected = [(i, r) for i, r in results if r.get("preliminary") not in accepted]
    if rejected:
        summary = "\n".join(
            f"  [{i}] {r.get('sender', '?')}: {r.get('preliminary', r.get('error', '?'))}" for i, r in rejected[:10]
        )
        pytest.fail(f"{len(rejected)}/{n} payments rejected at submit:\n{summary}")
    queued = sum(1 for _, r in results if r.get("preliminary") == "terQUEUED")
    print(f"  --- {n - queued} applied, {queued} queued ---")

    tx_hashes = [r["hash"] for _, r in results]
    assert len(tx_hashes) == n

    # -- Phase 3: Wait for all transactions to be validated on-ledger --
    print(f"\n=== Phase 3: Waiting for {n} transactions to validate ===")
    time.sleep(10)
    pending = set(range(n))
    validated_txns: dict[int, dict] = {}
    deadline = time.time() + 120
    while pending and time.time() < deadline:
        still_pending = set()
        for i in list(pending):
            try:
                tx_resp = client.request(Tx(transaction=tx_hashes[i]))
                meta = tx_resp.result.get("meta", {})
                code = meta.get("TransactionResult")
                if code == "tesSUCCESS":
                    validated_txns[i] = tx_resp.result
                    continue
                if code is not None and code != "tesSUCCESS":
                    pytest.fail(f"Txn {i} failed on-ledger: {code}")
                still_pending.add(i)
            except Exception:
                still_pending.add(i)
        pending = still_pending
        print(f"  {len(validated_txns)}/{n} validated, {len(pending)} pending...")
        if pending:
            time.sleep(5)

    if pending:
        pytest.fail(f"{len(pending)}/{n} txns not validated after timeout: {sorted(pending)[:10]}")

    # Dump validated transaction details
    print("\n  --- Transaction details ---")
    for i in sorted(validated_txns):
        r = validated_txns[i]
        # xrpl-py nests tx fields under tx_json; fall back to top-level
        tx = r.get("tx_json", r)
        sender = tx.get("Account", "?")
        dest = tx.get("Destination", "?")
        amount = tx.get("DeliverMax", tx.get("Amount", "?"))
        fee = tx.get("Fee", "?")
        ledger = tx.get("ledger_index", r.get("ledger_index", r.get("inLedger", "?")))
        result = r.get("meta", {}).get("TransactionResult", "?")
        amount_xrp = f"{int(amount) / 1_000_000:,.0f}" if str(amount).isdigit() else str(amount)
        print(f"  [{i:>3}] {sender} → {dest}  {amount_xrp} XRP  fee={fee}  ledger={ledger}  {result}")
    print(f"  All {n} transactions confirmed on-ledger")

    # -- Phase 4: Verify final balances --
    print("\n=== Phase 4: Verifying final balances ===")
    # Each account sends XRP_AMOUNT and receives XRP_AMOUNT → net 0 XRP.
    # Each account pays one transaction fee → final = initial - fee.
    expected_balance = initial_balance - base_fee

    balance_errors = []
    for addr, _ in accounts:
        final = _get_balance(client, addr)
        ok = "✓" if final == expected_balance else "✗"
        print(f"  {ok} {addr}  {final:>15,} drops  ({final / 1_000_000:,.0f} XRP)")
        if final != expected_balance:
            diff = final - expected_balance
            balance_errors.append(f"  {addr}: expected {expected_balance}, got {final} (diff {diff})")

    if balance_errors:
        summary = "\n".join(balance_errors[:10])
        if len(balance_errors) > 10:
            summary += f"\n  ... and {len(balance_errors) - 10} more"
        pytest.fail(f"{len(balance_errors)}/{n} accounts have wrong balance:\n{summary}")

    print(f"  --- All {n} accounts: {expected_balance:,} drops (initial - {base_fee} fee) ---")
    print("\n=== SMOKE TEST PASSED ===")
