import logging
import random

import pytest
import xrpl
from xrpl.models import (
    IssuedCurrency,
    IssuedCurrencyAmount,
)
from xrpl.models.requests import LedgerData
from xrpl.models.transactions import (
    AccountSet,
    AccountSetAsfFlag,
    AccountSetFlag,
    Payment,
    TransactionFlag,
    TrustSet,
)

from generate_ledger import generate_seed
from generate_ledger.gen import compute_account_index

log = logging.getLogger(__name__)


# @pytest.fixture
# def account_vectors():
#     path = pathlib.Path(__file__).parents[1] / "data/account_vectors.json"
#     return json.loads(path.read_text())


class TestAccount:
    def test_compute_account_index(self, accounts_factory):
        """Test that computing account indexes works by comparing output to known indices"""

        alice, bob = accounts_factory()
        log.info(f"Got {alice=}")
        log.info(f"Got {bob=}")
        assert compute_account_index(alice["account_id"]) == alice["account_index"]
        assert compute_account_index(alice["account_id"]) != bob["account_index"]


class TestIssuer:
    @pytest.mark.algo("secp256k1")
    def test_compute_trustline_index(self, test_config, accounts_factory, algo):
        """Test that computing account indexes works by comparing output to known indices"""
        alice, bob = accounts_factory()
        alice_wallet = xrpl.wallet.Wallet.from_seed(alice["seed"], algorithm=xrpl.CryptoAlgorithm(algo))
        bob_wallet = xrpl.wallet.Wallet.from_seed(bob["seed"], algorithm=xrpl.CryptoAlgorithm(algo))
        issued_currency_amount = IssuedCurrencyAmount(
            currency="USD",
            issuer=alice_wallet.address,
            value="1000000000000000",
        )
        pass
        from xrpl.transaction import submit_and_wait

        client = xrpl.clients.JsonRpcClient(url="http://localhost:5005")
        as_txn = AccountSet(
            account=alice_wallet.address,
            set_flag=AccountSetAsfFlag.ASF_DEFAULT_RIPPLE,
        )
        result = submit_and_wait(transaction=as_txn, client=client, wallet=alice_wallet)
        ts_txn = TrustSet(
            account=bob_wallet.address,
            limit_amount=issued_currency_amount,
        )
        result = submit_and_wait(transaction=ts_txn, client=client, wallet=bob_wallet)
        ledger_index = result.result["ledger_index"]
        ld_request = LedgerData(ledger_index=ledger_index)
        ledger_data = client.request(ld_request)
        known_types = {"Amendments", "AccountRoot", "DirectoryNode", "NFTokenPage", "MPTokenIssuance"}
        trustlines = [i for i in ledger_data.result["state"] if i["LedgerEntryType"] == "RippleState"]
        tl = [i for i in trustlines if alice_wallet.address in {i["HighLimit"]["issuer"], i["LowLimit"]["issuer"]}]
