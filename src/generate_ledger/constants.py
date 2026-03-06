"""Shared XRPL ledger object constants."""

# AccountRoot flags
LSF_DISABLE_MASTER = 0x00100000  # lsfDisableMaster: disables master key
LSF_DEFAULT_RIPPLE = 0x00800000  # lsfDefaultRipple: enables rippling (required for token issuers)
LSF_DEPOSIT_AUTH = 0x01000000  # lsfDepositAuth: requires deposit authorization

# AMM pseudo-account flags (combination)
AMM_ACCOUNT_FLAGS = LSF_DISABLE_MASTER | LSF_DEFAULT_RIPPLE | LSF_DEPOSIT_AUTH

# RippleState (trustline) flags
# IMPORTANT: lsfAMMNode is 0x01000000, NOT 0x02000000!
# 0x02000000 is lsfLowDeepFreeze which would freeze the trustline.
# lsfAMMNode happens to share the same bit value as lsfDepositAuth (account flag)
# but they live on different ledger entry types.
LSF_AMM_NODE = 0x01000000  # lsfAMMNode: marks trustlines owned by an AMM

# Transaction signing prefix
TXN_PREFIX = bytes.fromhex("54584E00")  # "TXN\0" — used before signing/hashing transactions

# XRPL neutral issuer address (used as issuer in Balance fields of RippleState)
NEUTRAL_ISSUER = "rrrrrrrrrrrrrrrrrrrrBZbvji"
