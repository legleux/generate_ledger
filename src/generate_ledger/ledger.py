from collections import UserString
from enum import Enum


class LedgerIndex(UserString):
    __slots__ = ()


class LedgerNamespace(Enum):
    ACCOUNT                        = b"a"
    AMENDMENTS                     = b"f"
    AMM                            = b"A"
    BOOK_DIR                       = b"B"
    BRIDGE                         = b"H"
    CHECK                          = b"C"
    CREDENTIAL                     = b"D"
    DELEGATE                       = b"E"
    DEPOSIT_PREAUTH                = b"p"
    DEPOSIT_PREAUTH_CREDENTIALS    = b"P"
    DID                            = b"I"
    DIR_NODE                       = b"d"
    ESCROW                         = b"u"
    FEE_SETTINGS                   = b"e"
    MPTOKEN                        = b"t"
    MPTOKEN_ISSUANCE               = b"~"
    NEGATIVE_UNL                   = b"N"
    NFTOKEN_BUY_OFFERS             = b"h"
    NFTOKEN_OFFER                  = b"q"
    NFTOKEN_SELL_OFFERS            = b"i"
    OFFER                          = b"o"
    ORACLE                         = b"R"
    OWNER_DIR                      = b"O"
    PERMISSIONED_DOMAIN            = b"m"
    SIGNER_LIST                    = b"S"
    SKIP_LIST                      = b"s"
    TICKET                         = b"T"
    TRUST_LINE                     = b"r"
    VAULT                          = b"V"
    XCHAIN_CLAIM_ID                = b"Q"
    XCHAIN_CREATE_ACCOUNT_CLAIM_ID = b"K"
    XRP_PAYMENT_CHANNEL            = b"x"

    @property
    def hex(self):
        return self.encode("utf-8").hex()
