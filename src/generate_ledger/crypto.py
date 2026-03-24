"""XRPL cryptographic primitives.

Thin wrappers around hashlib. Candidates for eventual replacement by
xrpl-py's ``xrpl.core.keypairs.helpers.sha512_first_half`` once that
function is part of the public API, or for upstreaming to xrpl-py.
"""

import hashlib


def sha512_half(data: bytes) -> bytes:
    """First 32 bytes of SHA-512 — the XRPL 'SHA512Half' operation."""
    return hashlib.sha512(data).digest()[:32]


def ripesha(data: bytes) -> bytes:
    """RIPEMD160(SHA256(data)) — used for XRPL account ID derivation."""
    sha256_hash = hashlib.sha256(data).digest()
    ripemd160 = hashlib.new("ripemd160")
    ripemd160.update(sha256_hash)
    return ripemd160.digest()


# TODO: remove sign_and_hash_txn entirely once confirmed rippled ignores PreviousTxnID on genesis ledger objects
# def sign_and_hash_txn(txn, seed: str, algorithm: str = "secp256k1") -> str:
#     """Sign an xrpl-py Transaction and return its transaction ID (SHA512Half hash)."""
#     ...  # was: Wallet.from_seed → encode_for_signing → sign → encode → sha512_half(TXN_PREFIX + blob)
