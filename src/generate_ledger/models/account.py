from __future__ import annotations  # until 3.14

import logging
from dataclasses import dataclass, field
from functools import wraps
from typing import Optional

from xrpl.asyncio.account import get_balance
from xrpl.asyncio.clients import AsyncJsonRpcClient
from xrpl.asyncio.transaction import sign_and_submit
from xrpl.models import (
    IssuedCurrencyAmount,
)
from xrpl.models.amounts import (
    is_issued_currency,
    is_mpt,
    is_xrp,
)
from xrpl.models.currencies import XRP, IssuedCurrency
from xrpl.models.requests import AccountCurrencies, AccountLines
from xrpl.models.requests.request import Request
from xrpl.models.response import ResponseStatus
from xrpl.models.transactions import (
    AccountSet,
    AccountSetAsfFlag,
    Payment,
    TrustSet,
)
from xrpl.wallet import Wallet

log = logging.getLogger(__name__)


def needs_client(method):
    @wraps(method)
    async def wrapper(self, *method_args, **method_kwargs):
        if self.client is None:
            log.exception("I'm sorry Dave, I can't do that. I have no client.")
        else:
            return await method(self, *method_args, **method_kwargs)

    return wrapper


def short_address(address):
    return "..".join([address[:6], address[-5:]])


default_trust_value = int(1e15)
default_trust_value = int(1e15)


# @dataclass(kw_only=True)
@dataclass
class Account:
    wallet: Wallet
    address: str = field(init=False)
    balances: dict = field(default_factory=dict)
    _currencies: dict = field(default_factory=dict)
    client: AsyncJsonRpcClient = field(default=None)
    with_client: str | None = field(default=None)

    def __post_init__(self):
        self.address = self.wallet.address
        if self.with_client:
            self.get_client(url=self.with_client)

    async def request(self, request: Request):
        try:
            response = await self.client.request(request)
            if response.status == ResponseStatus.SUCCESS:
                result = response.result
            elif response.status == ResponseStatus.ERROR:
                print("Something went wrong")
                result = "Error"
                raise Exception("Account.client error")
        except Exception as e:
            print(e)
        return result

    @needs_client
    async def get_trustline_currencies(self):
        al_response = await self.request(AccountLines(account=self.address))
        # self._currencies = al_response["lines"]
        return al_response["lines"]

    # TODO: How to conditionally apply/activate/enable this method iff self.client is valid?
    @needs_client
    async def get_currencies(self):
        xrp = await get_balance(self.address, self.client)
        issued_currencies = await self.get_trustline_currencies()

        #  TODO: Call update_balances() everytime this is called.
        # TODO: Hmm, a "ledger" class for accounting?
        return (xrp, issued_currencies)

    # @property
    # def currencies(self):
    #     return self._currencies

    def update_balances(self):
        # account_2_token_balance = [t for t in account_2_held_tokens[amount.issuer] if t.currency == amount.currency]
        for c in self.currencies:
            print("checking...")
            # log.info("Checking %s balance of %s", self.address, c)

    def get_client(self, url):
        """A handle on a client so network calls can be made"""
        self.client = AsyncJsonRpcClient(url)

    def __str__(self) -> str:
        return short_address(self.address)

    async def trust(self, currency: IssuedCurrency):
        ica = currency.to_amount(default_trust_value)
        ts_txn = TrustSet(account=self.address, limit_amount=ica)
        response = await sign_and_submit(ts_txn, self.client, self.wallet)
        return response

    async def pay(self, destination: Account, amount: IssuedCurrencyAmount | XRP):
        if is_xrp(amount):
            pass
        elif is_issued_currency(amount):
            pass
        elif is_mpt(amount):
            pass
        else:
            raise Exception(f"Can't handle {amount}")
        p_txn = Payment(account=self.address, amount=amount, destination=destination.address)
        response = await sign_and_submit(p_txn, self.client, self.wallet)
        return response

    # async def submit_txn(self, txn):

    @property
    def nfts(self) -> set:
        return self._nfts

    @nfts.setter
    def nfts(self, value: set) -> None:
        self._nfts = value

    @property
    def tickets(self) -> set:
        return self._tickets

    @tickets.setter
    def tickets(self, value: set) -> None:
        self._tickets = value


# @dataclass
# class Gateway(BaseAccount):
#     issued_currencies: dict = field(default_factory=dict)


# # @dataclass(kw_only=True)
# @dataclass
# class Account(BaseAccount):
#     # balances: dict = field(default_factory=dict)

#     # _tickets: set = field(default_factory=set)
#     # _nfts: set = field(default_factory=set)

#     # def __post_init__(self, **kwargs):
#     # super().__init__(kwargs)

# def trust(self, Account):
#     pass

# @property
# def nfts(self) -> set:
#     return self._nfts

# @nfts.setter
# def nfts(self, value: set) -> None:
#     self._nfts = value

# @property
# def tickets(self) -> set:
#     return self._tickets

# @tickets.setter
# def tickets(self, value: set) -> None:
#     self._tickets = value


@dataclass
class NFT:
    owner: Account
    nftoken_id: str


@dataclass
class Amm:
    account: str
    assets: list[IssuedCurrency]
    lp_token: list[IssuedCurrency]
