import asyncio
import logging
import random

import pytest
import xrpl
from xrpl.models import (
    IssuedCurrency,
    IssuedCurrencyAmount,
)
from xrpl.models.requests import Fee, LedgerData, ServerInfo
from xrpl.models.transactions import (
    AccountSet,
    AccountSetAsfFlag,
    AccountSetFlag,
    Payment,
    TransactionFlag,
    TrustSet,
)

from generate_ledger import generate_seed
from generate_ledger.gen import compute_account_index, generate_trustline
from generate_ledger.models.account import Account

log = logging.getLogger(__name__)


# @pytest.fixture
# def account_vectors():
#     path = pathlib.Path(__file__).parents[1] / "data/account_vectors.json"
#     return json.loads(path.read_text())

url = "http://172.18.0.5:5005"
url = "http://localhost:5005"

# pytest_plugins = ("pytest_asyncio",)


def test_generate_trustline(ripplestate_vectors):
    tlc = ripplestate_vectors
    hi = "rMxUGGVU1kTVBygGsWD725LEwsN4NFh45K"
    lo = "rfF5dorBvnBoyxi9TzPCpeoYCVUDobWmxA"
    currency = "USD"
    hi_amount = "1000000000000000"
    lo_amount = "0"
    tl = generate_trustline(hi, lo, currency, hi_amount, lo_amount)
    # pass
    # for k in tlc[0].keys():
    #     if tlc[0][k] != tl[k]:
    #         pass
    # pass
    assert tl == tlc, "Don't matches!"


@pytest.mark.algo("secp256k1")
@pytest.mark.asyncio
class TestCreateTrustline:
    async def test_trustline(self, accounts_factory, algo):
        """Test that trustline indexes works by comparing output to known indices"""
        gw, alice__, bob__ = accounts_factory(3)
        gateway_ = xrpl.wallet.Wallet.from_seed(gw["seed"], algorithm=algo)
        alice = xrpl.wallet.Wallet.from_seed(alice__["seed"], algorithm=algo)
        bob = Account(xrpl.wallet.Wallet.from_seed(bob__["seed"], algorithm=algo))
        gateway = Account(gateway_, with_client="")
        gateway.get_client(url)
        response = await gateway.request(Fee())
        alice = Account(alice, with_client=url)
        pass
        # Make sure Alice has rippling enabled
        # TODO: enable default rippling flag on accounts_factory()
        # create a trustline for USD from Alice to Bob
        # ica_usd = IssuedCurrencyAmount("USD", alice.address, "10000")
        default_limit = "1000000000000"
        default_payment = "100"
        gw_usd = IssuedCurrency(currency="USD", issuer=gateway.address)
        ica_usd_limit = gw_usd.to_amount(default_limit)
        alice_usd_gw_payment = gw_usd.to_amount(default_payment)
        response = await alice.trust(gw_usd)
        response = await gateway.pay(alice, alice_usd_gw_payment)
        response = await gateway.pay(alice, "100000000")
        alice_currencies = await alice.get_currencies()
        for c in alice_currencies[1]:
            pass
        # print(alice.balances)
        pass
        # assert alice has alice_usd_gw_payment
