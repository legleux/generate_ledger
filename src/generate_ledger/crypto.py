"""XRPL cryptographic primitives.

Thin wrappers around hashlib. Candidates for eventual replacement by
xrpl-py's ``xrpl.core.keypairs.helpers.sha512_first_half`` once that
function is part of the public API, or for upstreaming to xrpl-py.
"""

import hashlib
from binascii import unhexlify


def sha512_half(data: bytes) -> bytes:
    """First 32 bytes of SHA-512 — the XRPL 'SHA512Half' operation."""
    return hashlib.sha512(data).digest()[:32]


def ripesha(data: bytes) -> bytes:
    """RIPEMD160(SHA256(data)) — used for XRPL account ID derivation."""
    sha256_hash = hashlib.sha256(data).digest()
    ripemd160 = hashlib.new("ripemd160")
    ripemd160.update(sha256_hash)
    return ripemd160.digest()


def sign_and_hash_txn(txn, seed: str, algorithm: str = "secp256k1") -> str:
    """Sign an xrpl-py Transaction and return its transaction ID (SHA512Half hash).

    Args:
        txn: An xrpl-py Transaction object (e.g. TrustSet, AMMCreate).
        seed: The account seed (base58).
        algorithm: "ed25519" or "secp256k1".

    Returns:
        64-char uppercase hex transaction ID.
    """
    from xrpl import CryptoAlgorithm  # noqa: PLC0415
    from xrpl.core.binarycodec import encode, encode_for_signing  # noqa: PLC0415
    from xrpl.core.keypairs import sign  # noqa: PLC0415
    from xrpl.wallet import Wallet  # noqa: PLC0415

    from generate_ledger.constants import TXN_PREFIX  # noqa: PLC0415

    algo = CryptoAlgorithm.ED25519 if algorithm == "ed25519" else CryptoAlgorithm.SECP256K1
    wallet = Wallet.from_seed(seed, algorithm=algo)

    signing_payload_hex = encode_for_signing(txn.to_xrpl())
    signature_hex = sign(bytes.fromhex(signing_payload_hex), wallet.private_key)
    signed_dict = {**txn.to_xrpl(), "TxnSignature": signature_hex}
    tx_blob = encode(signed_dict)
    return sha512_half(TXN_PREFIX + unhexlify(tx_blob)).hex().upper()
