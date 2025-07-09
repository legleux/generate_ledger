from collections import UserString
from enum import StrEnum


class LedgerIndex(UserString):
    __slots__ = ()


class LedgerNamespace(StrEnum):
    ACCOUNT = "a"
    DIR_NODE = "d"
    TRUST_LINE = "r"
    OFFER = "o"
    OWNER_DIR = "O"
    BOOK_DIR = "B"
    SKIP_LIST = "s"
    ESCROW = "u"
    AMENDMENTS = "f"
    FEE_SETTINGS = "e"
    TICKET = "T"
    SIGNER_LIST = "S"
    XRP_PAYMENT_CHANNEL = "x"
    CHECK = "C"
    DEPOSIT_PREAUTH = "p"
    DEPOSIT_PREAUTH_CREDENTIALS = "P"
    NEGATIVE_UNL = "N"
    NFTOKEN_OFFER = "q"
    NFTOKEN_BUY_OFFERS = "h"
    NFTOKEN_SELL_OFFERS = "i"
    AMM = "A"
    BRIDGE = "H"
    XCHAIN_CLAIM_ID = "Q"
    XCHAIN_CREATE_ACCOUNT_CLAIM_ID = "K"
    DID = "I"
    ORACLE = "R"
    MPTOKEN_ISSUANCE = "~"
    MPTOKEN = "t"
    CREDENTIAL = "D"
    PERMISSIONED_DOMAIN = "m"
    DELEGATE = "E"
    VAULT = "V"

    @property
    def hex(self):
        return self.encode("utf-8").hex()
