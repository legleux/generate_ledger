"""Smoke test: gateway issues IOU to holder, verify trustline balance sign.

The most basic IOU test: a gateway sends issued currency to a holder
and we verify the balance is correct from both perspectives.

Uses a single xrpld node in standalone mode (no consensus needed).

Requires Docker. Skipped by default -- run with:
    pytest tests/smoke/test_trustline_balance.py -m smoke --no-cov -v -s
"""

import asyncio
import subprocess
import time

import pytest
from xrpl.asyncio.clients import AsyncJsonRpcClient
from xrpl.asyncio.transaction import autofill_and_sign, submit
from xrpl.models import IssuedCurrencyAmount, Payment
from xrpl.models.requests import AccountLines, Tx
from xrpl.wallet import Wallet

from tests.smoke.helpers import STANDALONE_CFG, ledger_accept

pytestmark = pytest.mark.smoke


@pytest.fixture(scope="module")
def rpc_port():
    return 5010


@pytest.fixture(scope="module")
def testnet_dir(tmp_path_factory):
    """Generate a ledger with 1 gateway and 1 holder."""
    output_dir = tmp_path_factory.mktemp("smoke_trustline")

    subprocess.run(
        [
            "uv",
            "run",
            "gen",
            "ledger",
            "--accounts",
            "1",
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


def test_trustline_balance(accounts, network, rpc_port):
    """Gateway sends 100 USD to holder; verify balance from both perspectives."""
    client = network
    rpc_url = f"http://localhost:{rpc_port}"

    gateway_addr, gateway_seed = accounts[0]
    _holder_addr, _holder_seed = accounts[1]
    holder_addr = _holder_addr

    print(f"\nGateway: {gateway_addr}")
    print(f"Holder:  {holder_addr}")

    # Send 100 USD from gateway to holder
    async def send_payment():
        ac = AsyncJsonRpcClient(rpc_url)
        wallet = Wallet.from_seed(gateway_seed)
        txn = Payment(
            account=gateway_addr,
            destination=holder_addr,
            amount=IssuedCurrencyAmount(currency="USD", issuer=gateway_addr, value="100"),
        )
        signed = await autofill_and_sign(txn, ac, wallet)
        response = await submit(signed, ac)
        return response.result

    result = asyncio.run(send_payment())
    preliminary = result.get("engine_result", "")
    tx_hash = result.get("tx_json", {}).get("hash", "")
    print(f"  Payment: {preliminary}  hash={tx_hash[:16]}...")
    assert preliminary == "tesSUCCESS", f"Payment rejected: {result}"

    # Close ledger and wait for validation
    deadline = time.time() + 30
    while time.time() < deadline:
        ledger_accept(client)
        try:
            resp = client.request(Tx(transaction=tx_hash))
            code = resp.result.get("meta", {}).get("TransactionResult")
            if code == "tesSUCCESS":
                print(f"  Validated: {code}")
                break
            if code is not None and code != "tesSUCCESS":
                pytest.fail(f"Payment failed on-ledger: {code}")
        except Exception:
            pass
        time.sleep(0.5)
    else:
        pytest.fail("Payment not validated after 30s")

    # Verify balance from holder's perspective
    resp = client.request(AccountLines(account=holder_addr, peer=gateway_addr))
    holder_lines = {line["currency"]: line["balance"] for line in resp.result.get("lines", [])}
    print(f"  Holder account_lines: USD={holder_lines.get('USD')}")
    assert holder_lines.get("USD") is not None, "Holder should have a USD trustline"
    assert float(holder_lines["USD"]) == 100, f"Holder should have 100 USD, got {holder_lines['USD']}"

    # Verify balance from gateway's perspective (opposite sign)
    resp = client.request(AccountLines(account=gateway_addr, peer=holder_addr))
    gw_lines = {line["currency"]: line["balance"] for line in resp.result.get("lines", [])}
    print(f"  Gateway account_lines: USD={gw_lines.get('USD')}")
    assert gw_lines.get("USD") is not None, "Gateway should have a USD trustline"
    assert float(gw_lines["USD"]) == -100, f"Gateway should show -100 USD (issued), got {gw_lines['USD']}"

    print("\n=== TRUSTLINE BALANCE SMOKE TEST PASSED ===")
