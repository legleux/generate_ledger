"""Fast cryptographic backends for XRPL account generation.

Provides native C-library backends (PyNaCl/libsodium for ed25519) with
automatic fallback to xrpl-py's pure-Python implementation.

Performance:
    NativeEd25519Backend (PyNaCl):  ~22,000 accounts/sec
    FallbackBackend (xrpl-py):      ~60 accounts/sec (secp256k1)
                                    ~80 accounts/sec (ed25519)
"""

import hashlib
import os
from abc import ABC, abstractmethod
from enum import Enum

import base58
from xrpl.core.addresscodec import encode_classic_address


class Algorithm(Enum):
    """Supported cryptographic algorithms."""
    SECP256K1 = "secp256k1"
    ED25519 = "ed25519"


class CryptoBackend(ABC):
    """Abstract interface for XRPL account generation."""

    @property
    @abstractmethod
    def algorithm(self) -> Algorithm:
        ...

    @abstractmethod
    def generate_account(self) -> tuple[str, str]:
        """Generate a new account.

        Returns:
            (base58_seed, address) tuple. The seed is in XRPL "s..." format,
            importable via xrpl-py's Wallet.from_seed().
        """
        ...


def _sha512_half(data: bytes) -> bytes:
    """SHA-512 Half: first 32 bytes of SHA-512 digest."""
    return hashlib.sha512(data).digest()[:32]


def _account_id_from_pubkey(public_key: bytes, algorithm: Algorithm) -> bytes:
    """Compute 20-byte XRPL account ID from raw public key bytes."""
    if algorithm == Algorithm.ED25519:
        key_bytes = b"\xed" + public_key
    else:
        key_bytes = public_key
    sha256_hash = hashlib.sha256(key_bytes).digest()
    ripemd160 = hashlib.new("ripemd160")
    ripemd160.update(sha256_hash)
    return ripemd160.digest()


def hex_to_base58_seed(hex_seed: str) -> str:
    """Convert 16-byte hex seed to XRPL base58 seed format ("s..." string).

    The XRPL seed format is: version_byte(0x21) + 16_bytes + 4_byte_checksum,
    Base58-encoded with the XRP alphabet.
    """
    seed_bytes = bytes.fromhex(hex_seed)
    versioned = b"\x21" + seed_bytes
    checksum = hashlib.sha256(hashlib.sha256(versioned).digest()).digest()[:4]
    return base58.b58encode(versioned + checksum, alphabet=base58.XRP_ALPHABET).decode()


class NativeEd25519Backend(CryptoBackend):
    """Ed25519 using PyNaCl (libsodium). ~22,000 accounts/sec."""

    def __init__(self) -> None:
        import nacl.signing  # noqa: PLC0415

        self._signing = nacl.signing

    @property
    def algorithm(self) -> Algorithm:
        return Algorithm.ED25519

    def generate_account(self) -> tuple[str, str]:
        # 1. Generate 16-byte XRPL seed entropy
        entropy = os.urandom(16)
        # 2. Derive ed25519 signing key (matches xrpl-py / rippled derivation)
        signing_key_bytes = _sha512_half(entropy)
        # 3. Get public key via PyNaCl (fast C library)
        signing_key = self._signing.SigningKey(signing_key_bytes)
        public_key = bytes(signing_key.verify_key)
        # 4. Compute XRPL address
        acct_id = _account_id_from_pubkey(public_key, Algorithm.ED25519)
        address = encode_classic_address(acct_id)
        # 5. Encode seed as base58 "s..." format
        seed = hex_to_base58_seed(entropy.hex())
        return seed, address


class FallbackBackend(CryptoBackend):
    """Fallback using xrpl-py (pure Python). Works for all algorithms."""

    def __init__(self, algorithm: Algorithm) -> None:
        from xrpl import CryptoAlgorithm  # noqa: PLC0415
        from xrpl.core.keypairs import generate_seed  # noqa: PLC0415
        from xrpl.wallet import Wallet  # noqa: PLC0415

        self._algorithm = algorithm
        self._xrpl_algo = (
            CryptoAlgorithm.ED25519
            if algorithm == Algorithm.ED25519
            else CryptoAlgorithm.SECP256K1
        )
        self._Wallet = Wallet
        self._generate_seed = generate_seed

    @property
    def algorithm(self) -> Algorithm:
        return self._algorithm

    def generate_account(self) -> tuple[str, str]:
        seed = self._generate_seed(algorithm=self._xrpl_algo)
        wallet = self._Wallet.from_seed(seed, algorithm=self._xrpl_algo)
        return seed, wallet.address


def get_backend(algo: Algorithm) -> CryptoBackend:
    """Get the best available backend for the given algorithm.

    For ed25519: returns NativeEd25519Backend if PyNaCl is installed,
    otherwise FallbackBackend.

    For secp256k1: always returns FallbackBackend (xrpl-py's secp256k1
    key derivation uses XRPL-specific sequence hashing that native
    libraries can't replicate without reimplementing the full algorithm).
    """
    if algo == Algorithm.ED25519:
        try:
            return NativeEd25519Backend()
        except ImportError:
            pass
    return FallbackBackend(algo)


def backend_info(algo: Algorithm) -> tuple[bool, str]:
    """Check if a native backend is available for the algorithm.

    Returns:
        (is_native, backend_name) tuple.
    """
    if algo == Algorithm.ED25519:
        try:
            import nacl.signing  # noqa: F401, PLC0415

            return (True, "pynacl")
        except ImportError:
            return (False, "xrpl-py")
    else:
        return (False, "xrpl-py")
