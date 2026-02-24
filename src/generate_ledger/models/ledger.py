from typing import NewType

NamespaceByte = NewType("NamespaceByte", int)

ACCOUNT                        = NamespaceByte(0x61)  # 'a'
AMENDMENTS                     = NamespaceByte(0x66)  # 'f'
AMM                            = NamespaceByte(0x41)  # 'A'
BOOK_DIR                       = NamespaceByte(0x42)  # 'B'
BRIDGE                         = NamespaceByte(0x48)  # 'H'
CHECK                          = NamespaceByte(0x43)  # 'C'
CREDENTIAL                     = NamespaceByte(0x44)  # 'D'
DELEGATE                       = NamespaceByte(0x45)  # 'E'
DEPOSIT_PREAUTH                = NamespaceByte(0x70)  # 'p'
DEPOSIT_PREAUTH_CREDENTIALS    = NamespaceByte(0x50)  # 'P'
DID                            = NamespaceByte(0x49)  # 'I'
DIR_NODE                       = NamespaceByte(0x64)  # 'd'
ESCROW                         = NamespaceByte(0x75)  # 'u'
FEE_SETTINGS                   = NamespaceByte(0x65)  # 'e'
MPTOKEN                        = NamespaceByte(0x74)  # 't'
MPTOKEN_ISSUANCE               = NamespaceByte(0x7E)  # '~'
NEGATIVE_UNL                   = NamespaceByte(0x4E)  # 'N'
NFTOKEN_BUY_OFFERS             = NamespaceByte(0x68)  # 'h'
NFTOKEN_OFFER                  = NamespaceByte(0x71)  # 'q'
NFTOKEN_SELL_OFFERS            = NamespaceByte(0x69)  # 'i'
OFFER                          = NamespaceByte(0x6F)  # 'o'
ORACLE                         = NamespaceByte(0x52)  # 'R'
OWNER_DIR                      = NamespaceByte(0x4F)  # 'O'
PERMISSIONED_DOMAIN            = NamespaceByte(0x6D)  # 'm'
SIGNER_LIST                    = NamespaceByte(0x53)  # 'S'
SKIP_LIST                      = NamespaceByte(0x73)  # 's'
TICKET                         = NamespaceByte(0x54)  # 'T'
TRUST_LINE                     = NamespaceByte(0x72)  # 'r'
VAULT                          = NamespaceByte(0x56)  # 'V'
XCHAIN_CLAIM_ID                = NamespaceByte(0x51)  # 'Q'
XCHAIN_CREATE_ACCOUNT_CLAIM_ID = NamespaceByte(0x4B)  # 'K'
XRP_PAYMENT_CHANNEL            = NamespaceByte(0x78)  # 'x'

def ns_prefix(ns: NamespaceByte) -> bytes:
    """XRPL index key prefix: 0x00 + code-byte."""
    return b"\x00" + bytes([ns])

def ns_hex(ns: NamespaceByte) -> str:
    """Convenience: '0061' for ACCOUNT, etc."""
    return ns_prefix(ns).hex().upper()
