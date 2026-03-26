"""Fast cryptographic backends for XRPL account generation.

Provides native C-library backends (PyNaCl/libsodium for ed25519,
coincurve/libsecp256k1 for secp256k1) with automatic fallback to
xrpl-py's pure-Python implementation.

Performance:
    NativeSecp256k1Backend (coincurve): ~6,000 accounts/sec
    NativeEd25519Backend (PyNaCl):      ~22,000 accounts/sec
    FallbackBackend (xrpl-py):          ~60 accounts/sec (secp256k1)
                                        ~80 accounts/sec (ed25519)
"""

import hashlib
import logging
import os
from abc import ABC, abstractmethod
from enum import Enum

import base58
from xrpl.core.addresscodec import encode_classic_address

log = logging.getLogger(__name__)


class Algorithm(Enum):
    """Supported cryptographic algorithms."""

    SECP256K1 = "secp256k1"
    ED25519 = "ed25519"


class CryptoBackend(ABC):
    """Abstract interface for XRPL account generation."""

    @property
    @abstractmethod
    def algorithm(self) -> Algorithm: ...

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


def hex_to_base58_seed(hex_seed: str, algorithm: Algorithm = Algorithm.SECP256K1) -> str:
    """Convert 16-byte hex seed to XRPL base58 seed format.

    secp256k1 seeds use version byte 0x21 → "s..." prefix.
    ed25519 seeds use version bytes [0x01, 0xE1, 0x4B] → "sEd..." prefix.
    """
    seed_bytes = bytes.fromhex(hex_seed)
    if algorithm == Algorithm.ED25519:
        version = b"\x01\xe1\x4b"
    else:
        version = b"\x21"
    versioned = version + seed_bytes
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
        # 2. Derive ed25519 signing key (matches xrpl-py / xrpld derivation)
        signing_key_bytes = _sha512_half(entropy)
        # 3. Get public key via PyNaCl (fast C library)
        signing_key = self._signing.SigningKey(signing_key_bytes)
        public_key = bytes(signing_key.verify_key)
        # 4. Compute XRPL address
        acct_id = _account_id_from_pubkey(public_key, Algorithm.ED25519)
        address = encode_classic_address(acct_id)
        # 5. Encode seed as base58 "s..." format
        seed = hex_to_base58_seed(entropy.hex(), Algorithm.ED25519)
        return seed, address


_SECP256K1_ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
_INTERMEDIATE_PADDING = b"\x00\x00\x00\x00"


class NativeSecp256k1Backend(CryptoBackend):
    """secp256k1 using coincurve (libsecp256k1).

    Implements the full XRPL 3-pass key derivation:
      1. Root keypair:  SHA512Half(seed + seq) → EC multiply
      2. Mid keypair:   SHA512Half(root_pub + padding + seq) → EC multiply
      3. Final keypair: (root_priv + mid_priv) mod n, point addition
    """

    def __init__(self) -> None:
        import coincurve  # noqa: PLC0415

        self._coincurve = coincurve

    @property
    def algorithm(self) -> Algorithm:
        return Algorithm.SECP256K1

    def _derive_secret(self, base: bytes, use_padding: bool = False) -> int:
        """Find a valid secp256k1 private key via the XRPL sequence hashing loop."""
        for seq in range(0xFFFFFFFF + 1):
            seq_bytes = seq.to_bytes(4, byteorder="big")
            if use_padding:
                candidate = _sha512_half(base + _INTERMEDIATE_PADDING + seq_bytes)
            else:
                candidate = _sha512_half(base + seq_bytes)
            secret = int.from_bytes(candidate, "big")
            if 0 < secret < _SECP256K1_ORDER:
                return secret
        msg = "Failed to derive valid secret"
        raise RuntimeError(msg)

    def generate_account(self) -> tuple[str, str]:
        # 1. Generate 16-byte XRPL seed entropy
        entropy = os.urandom(16)
        # 2. Root keypair
        root_secret = self._derive_secret(entropy)
        root_key = self._coincurve.PrivateKey(root_secret.to_bytes(32, "big"))
        root_pub_compressed = root_key.public_key.format(compressed=True)
        # 3. Intermediate keypair (derived from root public key)
        mid_secret = self._derive_secret(root_pub_compressed, use_padding=True)
        # 4. Final private key = (root + mid) mod order
        final_secret = (root_secret + mid_secret) % _SECP256K1_ORDER
        final_key = self._coincurve.PrivateKey(final_secret.to_bytes(32, "big"))
        final_pub = final_key.public_key.format(compressed=True)
        # 5. Compute XRPL address
        acct_id = _account_id_from_pubkey(final_pub, Algorithm.SECP256K1)
        address = encode_classic_address(acct_id)
        # 6. Encode seed
        seed = hex_to_base58_seed(entropy.hex(), Algorithm.SECP256K1)
        return seed, address


class FallbackBackend(CryptoBackend):
    """Fallback using xrpl-py (pure Python). Works for all algorithms."""

    def __init__(self, algorithm: Algorithm) -> None:
        from xrpl import CryptoAlgorithm  # noqa: PLC0415
        from xrpl.core.keypairs import generate_seed  # noqa: PLC0415
        from xrpl.wallet import Wallet  # noqa: PLC0415

        self._algorithm = algorithm
        self._xrpl_algo = CryptoAlgorithm.ED25519 if algorithm == Algorithm.ED25519 else CryptoAlgorithm.SECP256K1
        self._Wallet = Wallet
        self._generate_seed = generate_seed

    @property
    def algorithm(self) -> Algorithm:
        return self._algorithm

    def generate_account(self) -> tuple[str, str]:
        seed = self._generate_seed(algorithm=self._xrpl_algo)
        wallet = self._Wallet.from_seed(seed, algorithm=self._xrpl_algo)
        return seed, wallet.address


def get_backend(algo: Algorithm, *, use_gpu: bool = False) -> CryptoBackend:
    """Get the best available backend for the given algorithm.

    For ed25519 with use_gpu=True: returns GpuEd25519Backend if CuPy is available.
    For ed25519: returns NativeEd25519Backend if PyNaCl is installed,
    otherwise FallbackBackend.

    For secp256k1: returns NativeSecp256k1Backend if coincurve is installed,
    otherwise FallbackBackend.
    """
    if algo == Algorithm.ED25519 and use_gpu:
        try:
            from generate_ledger.gpu_backend import GpuEd25519Backend  # noqa: PLC0415

            return GpuEd25519Backend()
        except ImportError:
            log.warning("--gpu requested but CuPy is not installed. Install with: uv sync --group gpu")
        except RuntimeError as e:
            log.warning("--gpu requested but GPU initialization failed: %s", e)
    if algo == Algorithm.ED25519:
        try:
            return NativeEd25519Backend()
        except ImportError:
            pass
    elif algo == Algorithm.SECP256K1:
        try:
            return NativeSecp256k1Backend()
        except ImportError:
            pass
    return FallbackBackend(algo)


def backend_info(algo: Algorithm, *, use_gpu: bool = False) -> tuple[bool, str]:
    """Check if a native backend is available for the algorithm.

    Returns:
        (is_native, backend_name) tuple.
    """
    if algo == Algorithm.ED25519 and use_gpu:
        try:
            import cupy  # noqa: F401, PLC0415

            return (True, "cupy-cuda")
        except ImportError:
            pass
    if algo == Algorithm.ED25519:
        try:
            import nacl.signing  # noqa: F401, PLC0415

            return (True, "pynacl")
        except ImportError:
            return (False, "xrpl-py")
    elif algo == Algorithm.SECP256K1:
        try:
            import coincurve  # noqa: F401, PLC0415

            return (True, "coincurve")
        except ImportError:
            return (False, "xrpl-py")
    return (False, "xrpl-py")
