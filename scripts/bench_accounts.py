#!/usr/bin/env python3
"""
Benchmark script for parallel account and trustline generation.

Tests different parallelization strategies for XRPL account generation
and trustline (RippleState + DirectoryNode) object generation,
compatible with Python 3.13t (free-threaded/no-GIL).

Architecture:
  1. Seeds/entropy are pre-generated (not timed) or loaded from file
  2. Keypair derivation uses native C libraries (PyNaCl, coincurve)
  3. Address encoding is modular (currently xrpl-py, replaceable)
  4. Trustline generation benchmarks in-memory object + index calculation

Usage:
    uv run scripts/bench_accounts.py -n 100 --mode seq
    uv run scripts/bench_accounts.py -n 100 --mode mp --workers 4
    uv run scripts/bench_accounts.py -n 100 --mode thread --workers 4
    uv run scripts/bench_accounts.py -n 1000 --algo ed25519 --mode mp

    # Use pre-generated seeds from file
    uv run scripts/bench_accounts.py --seeds-file seeds.txt --mode mp

    # Generate seeds only (no derivation)
    uv run scripts/bench_accounts.py -n 10000 --seeds-only --save-seeds seeds.txt

    # Benchmark trustline generation
    uv run scripts/bench_accounts.py -n 1000 --trustlines --mode mp
    uv run scripts/bench_accounts.py -n 100 --trustlines --topology mesh --mode mp
"""

import argparse
import hashlib
import json
import os
import random
import sys
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum

# Add src directory to path for standalone execution
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gl.indices import account_root_index


# =============================================================================
# Crypto Backend Abstraction
# =============================================================================

class Algorithm(Enum):
    """Supported cryptographic algorithms."""
    SECP256K1 = "secp256k1"
    ED25519 = "ed25519"


class TrustlineTopology(Enum):
    """Trustline connection topologies."""
    STAR = "star"      # All accounts trust account 0 (realistic for issued currencies)
    RING = "ring"      # Each account trusts the next
    MESH = "mesh"      # All pairs (n*(n-1)/2 trustlines)
    RANDOM = "random"  # Random pairs


@dataclass
class Keypair:
    """Generated keypair with all derived data."""
    public_key: bytes  # Raw public key bytes
    private_key: bytes  # Raw private key bytes
    seed: str  # Encoded seed (for export)
    address: str  # XRPL classic address
    index: str  # AccountRoot ledger index


@dataclass
class TrustlineObjects:
    """Generated trustline ledger objects."""
    ripple_state: dict
    directory_node_a: dict
    directory_node_b: dict
    rsi: str  # RippleState index


@dataclass
class TrustlinePair:
    """A trustline pair with currency."""
    addr_a: str
    addr_b: str
    currency: str


# =============================================================================
# Self-Contained Index Calculations (no generate_ledger dependency)
# =============================================================================

# Namespace constants
NS_TRUST_LINE = b"\x00\x72"  # 'r'
NS_OWNER_DIR = b"\x00\x4F"   # 'O'


def _sha512_half(data: bytes) -> bytes:
    """SHA512-Half: first 32 bytes of SHA512."""
    return hashlib.sha512(data).digest()[:32]


def _currency_to_160(code: str) -> bytes:
    """
    Convert a currency code to 20-byte representation.

    Accepts either:
      - a 3-letter ASCII code like "USD" (placed at bytes 12..14, others 0)
      - a 40-hex string (20 raw bytes), for non-standard/issued currencies
    """
    code = code.strip()
    # Is it hex form?
    if len(code) == 40 and all(c in "0123456789abcdefABCDEF" for c in code):
        return bytes.fromhex(code)
    # Standard 3-letter form
    if len(code) == 3 and code.isascii():
        b = bytearray(20)
        b[12:15] = code.encode("ascii")
        return bytes(b)
    raise ValueError(f"Invalid currency: {code}")


def _decode_account_id(address: str) -> bytes:
    """Classic address -> 20-byte AccountID via Base58Check decode."""
    import base58
    return base58.b58decode_check(address, alphabet=base58.XRP_ALPHABET)[1:]


def ripple_state_index(addr_a: str, addr_b: str, currency: str) -> str:
    """
    Compute RippleState ledger index.

    Formula: SHA512-Half(0x0072 + low_account + high_account + currency_160)
    """
    a1, a2 = _decode_account_id(addr_a), _decode_account_id(addr_b)
    low, high = (a1, a2) if a1 < a2 else (a2, a1)
    preimage = NS_TRUST_LINE + low + high + _currency_to_160(currency)
    return _sha512_half(preimage).hex().upper()


def owner_dir_index(address: str) -> str:
    """
    Compute owner directory index for an account.

    Formula: SHA512-Half(0x004F + account_id)
    """
    preimage = NS_OWNER_DIR + _decode_account_id(address)
    return _sha512_half(preimage).hex().upper()


# =============================================================================
# Trustline Object Generation
# =============================================================================

def generate_trustline_objects(
    addr_a: str,
    addr_b: str,
    currency: str,
    limit: int = 1_000_000,
    ledger_seq: int = 2,
) -> TrustlineObjects:
    """
    Generate RippleState + 2 DirectoryNodes for a trustline.

    Returns a TrustlineObjects containing:
    - ripple_state: The RippleState ledger object
    - directory_node_a: DirectoryNode for account A
    - directory_node_b: DirectoryNode for account B
    - rsi: The RippleState index (for reference)
    """
    rsi = ripple_state_index(addr_a, addr_b, currency)

    # Order accounts for Low/High fields
    a1, a2 = _decode_account_id(addr_a), _decode_account_id(addr_b)
    lo_addr, hi_addr = (addr_a, addr_b) if a1 < a2 else (addr_b, addr_a)

    ripple_state = {
        "LedgerEntryType": "RippleState",
        "Balance": {"currency": currency, "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji", "value": "0"},
        "Flags": 131072,
        "HighLimit": {"currency": currency, "issuer": hi_addr, "value": str(limit)},
        "LowLimit": {"currency": currency, "issuer": lo_addr, "value": str(limit)},
        "HighNode": "0",
        "LowNode": "0",
        "PreviousTxnID": "0" * 64,  # Placeholder for benchmarking
        "PreviousTxnLgrSeq": ledger_seq,
        "index": rsi,
    }

    # DirectoryNodes
    def make_dir_node(owner: str) -> dict:
        root_idx = owner_dir_index(owner)
        return {
            "LedgerEntryType": "DirectoryNode",
            "Flags": 0,
            "Indexes": [rsi],
            "Owner": owner,
            "RootIndex": root_idx,
            "index": root_idx,
            "PreviousTxnID": "0" * 64,
            "PreviousTxnLgrSeq": ledger_seq,
        }

    return TrustlineObjects(
        ripple_state=ripple_state,
        directory_node_a=make_dir_node(addr_a),
        directory_node_b=make_dir_node(addr_b),
        rsi=rsi,
    )


# =============================================================================
# Trustline Topology Generation
# =============================================================================

DEFAULT_CURRENCIES = ["USD"]


def generate_trustline_pairs(
    accounts: list[tuple[str, str, str]],  # (address, seed, index)
    topology: TrustlineTopology,
    currencies: list[str],
    random_fraction: float = 0.3,
) -> list[TrustlinePair]:
    """
    Generate trustline pairs based on topology.

    Args:
        accounts: List of (address, seed, index) tuples
        topology: Connection topology (star, ring, mesh, random)
        currencies: List of currency codes to create trustlines for
        random_fraction: For RANDOM topology, fraction of possible pairs (0.0-1.0)

    Returns:
        List of TrustlinePair (addr_a, addr_b, currency)
    """
    if len(accounts) < 2:
        return []

    pairs: list[TrustlinePair] = []
    addresses = [a[0] for a in accounts]
    n = len(addresses)

    for currency in currencies:
        if topology == TrustlineTopology.STAR:
            # All accounts trust account 0 (the "issuer")
            issuer = addresses[0]
            for i in range(1, n):
                pairs.append(TrustlinePair(issuer, addresses[i], currency))

        elif topology == TrustlineTopology.RING:
            # Each account trusts the next, forming a ring
            for i in range(n):
                pairs.append(TrustlinePair(addresses[i], addresses[(i + 1) % n], currency))

        elif topology == TrustlineTopology.MESH:
            # All pairs (n*(n-1)/2 trustlines per currency)
            for i in range(n):
                for j in range(i + 1, n):
                    pairs.append(TrustlinePair(addresses[i], addresses[j], currency))

        elif topology == TrustlineTopology.RANDOM:
            # Random subset of pairs
            all_pairs = []
            for i in range(n):
                for j in range(i + 1, n):
                    all_pairs.append((addresses[i], addresses[j]))
            # Select a fraction
            num_pairs = max(1, int(len(all_pairs) * random_fraction))
            selected = random.sample(all_pairs, min(num_pairs, len(all_pairs)))
            for addr_a, addr_b in selected:
                pairs.append(TrustlinePair(addr_a, addr_b, currency))

    return pairs


class CryptoBackend(ABC):
    """Abstract interface for cryptographic operations."""

    @abstractmethod
    def generate_seed(self) -> str:
        """Generate a random seed."""
        ...

    @abstractmethod
    def derive_keypair(self, seed: str) -> tuple[bytes, bytes]:
        """Derive (public_key, private_key) from seed."""
        ...

    @property
    @abstractmethod
    def algorithm(self) -> Algorithm:
        """Return the algorithm this backend uses."""
        ...


class AddressEncoder(ABC):
    """Abstract interface for address encoding (modular/replaceable)."""

    @abstractmethod
    def encode(self, public_key: bytes, algorithm: Algorithm) -> str:
        """Encode public key to XRPL classic address."""
        ...


# =============================================================================
# Native Crypto Backends
# =============================================================================

class NativeEd25519Backend(CryptoBackend):
    """Ed25519 using PyNaCl (libsodium) - ~50,000 keys/sec."""

    def __init__(self) -> None:
        try:
            import nacl.signing
            import nacl.encoding
            self._nacl_signing = nacl.signing
            self._nacl_encoding = nacl.encoding
        except ImportError as e:
            raise ImportError("PyNaCl required for ed25519. Install: pip install pynacl") from e

    @property
    def algorithm(self) -> Algorithm:
        return Algorithm.ED25519

    def generate_seed(self) -> str:
        """Generate random 32 bytes, hex encoded."""
        return os.urandom(32).hex()

    def derive_keypair(self, seed: str) -> tuple[bytes, bytes]:
        """Derive ed25519 keypair from seed."""
        seed_bytes = bytes.fromhex(seed)
        signing_key = self._nacl_signing.SigningKey(seed_bytes)
        public_key = bytes(signing_key.verify_key)
        private_key = bytes(signing_key)
        return (public_key, private_key)


class NativeSecp256k1Backend(CryptoBackend):
    """secp256k1 using coincurve (libsecp256k1) - ~15,000 keys/sec."""

    def __init__(self) -> None:
        try:
            import coincurve
            self._coincurve = coincurve
        except ImportError as e:
            raise ImportError("coincurve required for secp256k1. Install: pip install coincurve") from e

    @property
    def algorithm(self) -> Algorithm:
        return Algorithm.SECP256K1

    def generate_seed(self) -> str:
        """Generate random 32 bytes, hex encoded."""
        return os.urandom(32).hex()

    def derive_keypair(self, seed: str) -> tuple[bytes, bytes]:
        """Derive secp256k1 keypair from seed."""
        seed_bytes = bytes.fromhex(seed)
        private_key = self._coincurve.PrivateKey(seed_bytes)
        public_key = private_key.public_key.format(compressed=True)
        return (public_key, bytes(private_key.secret))


class FastEcdsaSecp256k1Backend(CryptoBackend):
    """secp256k1 using fastecdsa (GMP) - ~900 keys/sec."""

    def __init__(self) -> None:
        try:
            from fastecdsa import keys, curve
            from fastecdsa.encoding.sec1 import SEC1Encoder
            self._keys = keys
            self._curve = curve.secp256k1
            self._encoder = SEC1Encoder
        except ImportError as e:
            raise ImportError("fastecdsa required. Install: pip install fastecdsa") from e

    @property
    def algorithm(self) -> Algorithm:
        return Algorithm.SECP256K1

    def generate_seed(self) -> str:
        """Generate random 32 bytes, hex encoded."""
        return os.urandom(32).hex()

    def derive_keypair(self, seed: str) -> tuple[bytes, bytes]:
        """Derive secp256k1 keypair from seed."""
        seed_bytes = bytes.fromhex(seed)
        # Convert seed to integer for private key
        private_int = int.from_bytes(seed_bytes, 'big')
        # Ensure it's within curve order
        private_int = private_int % self._curve.q
        if private_int == 0:
            private_int = 1
        # Derive public key
        public_point = private_int * self._curve.G
        # Encode public key in compressed SEC1 format
        public_key = self._encoder.encode_public_key(public_point, compressed=True)
        return (public_key, seed_bytes)


class FallbackBackend(CryptoBackend):
    """Fallback using xrpl-py (pure Python ecpy) - ~60 keys/sec."""

    def __init__(self, algorithm: Algorithm) -> None:
        import base58
        from xrpl import CryptoAlgorithm
        from xrpl.core.keypairs import derive_keypair

        self._algorithm = algorithm
        self._xrpl_algo = (
            CryptoAlgorithm.ED25519 if algorithm == Algorithm.ED25519
            else CryptoAlgorithm.SECP256K1
        )
        self._derive_keypair = derive_keypair
        self._base58 = base58

    @property
    def algorithm(self) -> Algorithm:
        return self._algorithm

    def generate_seed(self) -> str:
        """Generate random 16 bytes as hex (matching XRPL seed entropy size)."""
        return os.urandom(16).hex()

    def _hex_to_base58_seed(self, hex_seed: str) -> str:
        """Convert hex seed to base58 XRPL seed format."""
        seed_bytes = bytes.fromhex(hex_seed)
        # XRPL seed version byte is 0x21
        versioned = b"\x21" + seed_bytes
        checksum = hashlib.sha256(hashlib.sha256(versioned).digest()).digest()[:4]
        return self._base58.b58encode(
            versioned + checksum, alphabet=self._base58.XRP_ALPHABET
        ).decode()

    def derive_keypair(self, seed: str) -> tuple[bytes, bytes]:
        """Derive keypair using xrpl-py (converts hex to base58 internally)."""
        # Check if seed is hex (32 chars = 16 bytes) or already base58
        if len(seed) == 32 and all(c in "0123456789abcdefABCDEF" for c in seed):
            base58_seed = self._hex_to_base58_seed(seed)
        else:
            # Assume it's already base58
            base58_seed = seed
        public_hex, private_hex = self._derive_keypair(base58_seed, algorithm=self._xrpl_algo)
        return (bytes.fromhex(public_hex), bytes.fromhex(private_hex))


# =============================================================================
# Address Encoding (Modular - can be replaced)
# =============================================================================

class XrplAddressEncoder(AddressEncoder):
    """
    XRPL address encoding.

    Currently uses xrpl-py, but implements the algorithm explicitly
    so it can be replaced with a pure implementation.

    Algorithm:
    1. For ed25519: prepend 0xED to 32-byte public key
    2. SHA256(public_key)
    3. RIPEMD160(SHA256 result) = 20-byte account ID
    4. Base58Check encode with version byte 0x00
    """

    def __init__(self, use_xrpl_py: bool = True) -> None:
        self._use_xrpl_py = use_xrpl_py
        if use_xrpl_py:
            from xrpl.core.addresscodec import encode_classic_address
            self._encode_classic_address = encode_classic_address

    def encode(self, public_key: bytes, algorithm: Algorithm) -> str:
        """Encode public key to XRPL classic address."""
        if self._use_xrpl_py:
            return self._encode_xrpl_py(public_key, algorithm)
        else:
            return self._encode_native(public_key, algorithm)

    def _encode_xrpl_py(self, public_key: bytes, algorithm: Algorithm) -> str:
        """Use xrpl-py for encoding."""
        # xrpl-py expects the key with ED prefix for ed25519
        if algorithm == Algorithm.ED25519:
            key_bytes = b'\xed' + public_key
        else:
            key_bytes = public_key

        # Compute account ID: RIPEMD160(SHA256(public_key))
        sha256_hash = hashlib.sha256(key_bytes).digest()
        ripemd160 = hashlib.new('ripemd160')
        ripemd160.update(sha256_hash)
        account_id = ripemd160.digest()

        return self._encode_classic_address(account_id)

    def _encode_native(self, public_key: bytes, algorithm: Algorithm) -> str:
        """Pure Python implementation (no xrpl-py dependency)."""
        import base58

        # Prepare public key
        if algorithm == Algorithm.ED25519:
            key_bytes = b'\xed' + public_key
        else:
            key_bytes = public_key

        # Compute account ID: RIPEMD160(SHA256(public_key))
        sha256_hash = hashlib.sha256(key_bytes).digest()
        ripemd160 = hashlib.new('ripemd160')
        ripemd160.update(sha256_hash)
        account_id = ripemd160.digest()

        # Base58Check with version byte 0x00
        versioned = b'\x00' + account_id
        checksum = hashlib.sha256(hashlib.sha256(versioned).digest()).digest()[:4]
        return base58.b58encode(versioned + checksum, alphabet=base58.XRP_ALPHABET).decode()


# =============================================================================
# Backend Factory
# =============================================================================

# Cache for backend availability
_BACKEND_CACHE: dict[Algorithm, tuple[bool, str]] = {}


def _check_backend_available(algo: Algorithm) -> tuple[bool, str]:
    """Check if native backend is available, return (available, name)."""
    if algo in _BACKEND_CACHE:
        return _BACKEND_CACHE[algo]

    if algo == Algorithm.ED25519:
        try:
            import nacl.signing  # noqa: F401
            result = (True, "pynacl")
        except ImportError:
            result = (False, "fallback")
    else:
        # Try coincurve first (fastest), then fastecdsa, then fallback
        try:
            import coincurve  # noqa: F401
            result = (True, "coincurve")
        except ImportError:
            try:
                from fastecdsa import keys  # noqa: F401
                result = (True, "fastecdsa")
            except ImportError:
                result = (False, "fallback")

    _BACKEND_CACHE[algo] = result
    return result


def get_backend(algo: Algorithm) -> CryptoBackend:
    """Get the best available backend for the algorithm."""
    available, name = _check_backend_available(algo)

    if algo == Algorithm.ED25519:
        if available:
            return NativeEd25519Backend()
        return FallbackBackend(algo)
    else:
        if name == "coincurve":
            return NativeSecp256k1Backend()
        elif name == "fastecdsa":
            return FastEcdsaSecp256k1Backend()
        return FallbackBackend(algo)


def get_address_encoder(use_native: bool = False) -> AddressEncoder:
    """Get address encoder."""
    return XrplAddressEncoder(use_xrpl_py=not use_native)


# =============================================================================
# Account Generation
# =============================================================================

# Global instances for multiprocessing (initialized per-process)
_BACKEND: CryptoBackend | None = None
_ENCODER: AddressEncoder | None = None
_ALGO: Algorithm | None = None


def _init_worker(algo: Algorithm) -> None:
    """Initialize worker process with backend and encoder."""
    global _BACKEND, _ENCODER, _ALGO
    _ALGO = algo
    _BACKEND = get_backend(algo)
    _ENCODER = get_address_encoder()


def _derive_account(seed: str) -> tuple[str, str, str]:
    """Derive account from seed using global backend/encoder."""
    assert _BACKEND is not None and _ENCODER is not None and _ALGO is not None
    public_key, _ = _BACKEND.derive_keypair(seed)
    address = _ENCODER.encode(public_key, _ALGO)
    index = account_root_index(address)
    return (address, seed, index)


def derive_account(seed: str, backend: CryptoBackend, encoder: AddressEncoder) -> tuple[str, str, str]:
    """Derive account from seed (explicit dependencies)."""
    public_key, _ = backend.derive_keypair(seed)
    address = encoder.encode(public_key, backend.algorithm)
    index = account_root_index(address)
    return (address, seed, index)


# =============================================================================
# Seed Generation / Loading
# =============================================================================

def generate_seeds(count: int, backend: CryptoBackend, quiet: bool) -> list[str]:
    """Generate random seeds."""
    if not quiet:
        print(f"  Generating {count} seeds...", file=sys.stderr)
    seeds = [backend.generate_seed() for _ in range(count)]
    if not quiet:
        print(f"  Seeds ready.", file=sys.stderr)
    return seeds


SEED_BINARY_MAGIC = b"XRPL_SEEDS\x00\x01"  # Magic header for binary seed files
SEED_BYTES_LEN = 32  # Raw seed length in bytes (hex seeds)
SEED_BYTES_LEN_BASE58 = 16  # Raw seed length for base58 seeds (after decoding)


def _seed_to_bytes(seed: str) -> bytes:
    """
    Convert a seed string to raw bytes for binary storage.

    Handles:
    - Hex strings (64 chars) -> 32 bytes (native ed25519/secp256k1 backends)
    - Hex strings (32 chars) -> 16 bytes (fallback backend)
    - Base58 XRPL seeds (s...) -> decode and return 16-byte payload
    """
    # Check if it's a hex string
    if all(c in "0123456789abcdefABCDEF" for c in seed):
        if len(seed) == 64:  # 32 bytes - native backends
            return bytes.fromhex(seed)
        if len(seed) == 32:  # 16 bytes - fallback backend
            return bytes.fromhex(seed)

    # Try base58 decode (XRPL seeds start with 's')
    if seed.startswith("s"):
        import base58
        try:
            decoded = base58.b58decode_check(seed, alphabet=base58.XRP_ALPHABET)
            # Skip version byte (0x21), return 16-byte payload
            return decoded[1:]
        except Exception:
            pass

    raise ValueError(f"Unknown seed format: {seed[:10]}...")


def _bytes_to_seed(data: bytes) -> str:
    """
    Convert raw bytes back to seed string (hex format for internal use).

    For consistency, we always return hex format internally, which works
    with both native backends and can be converted to base58 if needed.
    """
    return data.hex()


def load_seeds_from_file(filepath: str, quiet: bool) -> list[str]:
    """
    Load seeds from a file.

    Supported formats (auto-detected):
    - Binary: XRPL_SEEDS magic + concatenated 32-byte seeds (fastest)
    - Plain text: one seed per line (lines starting with # are ignored)
    - JSON array: ["seed1", "seed2", ...]
    - JSON object: {"seeds": [...]} or {"accounts": [{"seed": ...}, ...]}

    Seeds are returned as hex strings (64 chars) for internal use.
    """
    if not quiet:
        print(f"  Loading seeds from {filepath}...", file=sys.stderr)

    # Try binary format first
    with open(filepath, "rb") as f:
        header = f.read(len(SEED_BINARY_MAGIC))
        if header == SEED_BINARY_MAGIC:
            # Binary format: read seed length byte, then raw seed data
            seed_len_byte = f.read(1)
            if not seed_len_byte:
                raise ValueError("Invalid binary seed file: missing seed length byte")
            seed_len = seed_len_byte[0]
            raw_data = f.read()
            if len(raw_data) % seed_len != 0:
                raise ValueError(
                    f"Invalid binary seed file: {len(raw_data)} bytes "
                    f"not divisible by seed length {seed_len}"
                )
            seeds = [
                _bytes_to_seed(raw_data[i:i + seed_len])
                for i in range(0, len(raw_data), seed_len)
            ]
            if not quiet:
                print(f"  Loaded {len(seeds)} seeds (binary format).", file=sys.stderr)
            return seeds

    # Fall back to text formats
    with open(filepath) as f:
        content = f.read().strip()

    seeds: list[str] = []

    if content.startswith(("{", "[")):
        try:
            data = json.loads(content)
            if isinstance(data, list):
                seeds = [str(s) for s in data]
            elif isinstance(data, dict):
                if "seeds" in data:
                    seeds = [str(s) for s in data["seeds"]]
                elif "accounts" in data:
                    seeds = [str(a["seed"]) for a in data["accounts"] if "seed" in a]
                else:
                    raise ValueError("JSON object must have 'seeds' or 'accounts' key")
            else:
                raise ValueError("JSON must be an array or object")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}") from e
    else:
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                seeds.append(line)

    if not seeds:
        raise ValueError(f"No seeds found in {filepath}")

    if not quiet:
        print(f"  Loaded {len(seeds)} seeds (text format).", file=sys.stderr)

    return seeds


def save_seeds_to_file(
    seeds: list[str], filepath: str, quiet: bool, text_format: bool = False
) -> None:
    """
    Save seeds to a file.

    Args:
        seeds: List of seeds (hex strings or base58 encoded)
        filepath: Output file path
        quiet: Suppress progress output
        text_format: If True, save as text (one per line). Default is binary.

    Binary format is ~2-3x smaller and faster to read/write.
    """
    if text_format:
        with open(filepath, "w") as f:
            f.write("\n".join(seeds) + "\n")
        if not quiet:
            print(f"  Seeds saved to {filepath} (text format)", file=sys.stderr)
    else:
        # Binary format: magic header + seed_length (1 byte) + concatenated raw bytes
        # Determine seed byte length from first seed
        first_seed_bytes = _seed_to_bytes(seeds[0])
        seed_len = len(first_seed_bytes)

        with open(filepath, "wb") as f:
            f.write(SEED_BINARY_MAGIC)
            f.write(bytes([seed_len]))  # Store seed byte length
            for seed in seeds:
                seed_bytes = _seed_to_bytes(seed)
                if len(seed_bytes) != seed_len:
                    raise ValueError(f"Inconsistent seed lengths: {seed_len} vs {len(seed_bytes)}")
                f.write(seed_bytes)

        if not quiet:
            size_kb = (len(SEED_BINARY_MAGIC) + 1 + len(seeds) * seed_len) / 1024
            print(f"  Seeds saved to {filepath} (binary, {size_kb:.1f} KB)", file=sys.stderr)


# =============================================================================
# Execution Modes
# =============================================================================

def run_sequential(
    seeds: list[str], algo: Algorithm, workers: int, quiet: bool
) -> list[tuple[str, str, str]]:
    """Sequential derivation (baseline)."""
    del workers
    backend = get_backend(algo)
    encoder = get_address_encoder()
    results = []
    count = len(seeds)
    for i, seed in enumerate(seeds):
        results.append(derive_account(seed, backend, encoder))
        if not quiet and (i + 1) % 1000 == 0:
            print(f"  Derived {i + 1}/{count}...", file=sys.stderr)
    return results


def run_multiprocessing(
    seeds: list[str], algo: Algorithm, workers: int, quiet: bool
) -> list[tuple[str, str, str]]:
    """Multiprocessing using ProcessPoolExecutor."""
    count = len(seeds)
    with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker, initargs=(algo,)) as executor:
        results = []
        for i, result in enumerate(executor.map(_derive_account, seeds, chunksize=100)):
            results.append(result)
            if not quiet and (i + 1) % 1000 == 0:
                print(f"  Derived {i + 1}/{count}...", file=sys.stderr)
    return results


def run_threading(
    seeds: list[str], algo: Algorithm, workers: int, quiet: bool
) -> list[tuple[str, str, str]]:
    """Threading using ThreadPoolExecutor (benefits from 3.13t no-GIL)."""
    backend = get_backend(algo)
    encoder = get_address_encoder()
    count = len(seeds)

    def derive(seed: str) -> tuple[str, str, str]:
        return derive_account(seed, backend, encoder)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(derive, seed) for seed in seeds]
        results = []
        for i, future in enumerate(futures):
            results.append(future.result())
            if not quiet and (i + 1) % 1000 == 0:
                print(f"  Derived {i + 1}/{count}...", file=sys.stderr)
    return results


def _hybrid_process_batch(args: tuple[list[str], Algorithm, int]) -> list[tuple[str, str, str]]:
    """Process a batch of seeds with a thread pool (module-level for pickling)."""
    batch_seeds, batch_algo, num_threads = args
    backend = get_backend(batch_algo)
    encoder = get_address_encoder()

    def derive(seed: str) -> tuple[str, str, str]:
        return derive_account(seed, backend, encoder)

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        return list(executor.map(derive, batch_seeds))


def run_hybrid(
    seeds: list[str], algo: Algorithm, workers: int, quiet: bool
) -> list[tuple[str, str, str]]:
    """Hybrid mode: processes spawning thread pools."""
    count = len(seeds)
    process_workers = max(1, workers // 2)
    thread_workers = max(1, workers // process_workers)

    batch_size = (count + process_workers - 1) // process_workers
    batches = [seeds[i:i + batch_size] for i in range(0, count, batch_size)]
    batches = [b for b in batches if b]

    if not quiet:
        print(f"  Hybrid: {len(batches)} processes × {thread_workers} threads", file=sys.stderr)

    with ProcessPoolExecutor(max_workers=len(batches)) as executor:
        args_list = [(batch, algo, thread_workers) for batch in batches]
        batch_results = list(executor.map(_hybrid_process_batch, args_list))

    results = []
    for batch in batch_results:
        results.extend(batch)
    return results


def run_gpu(
    seeds: list[str], algo: Algorithm, workers: int, quiet: bool
) -> list[tuple[str, str, str]]:
    """
    GPU-accelerated keypair derivation (stub).

    Requires CUDA kernels for EC operations. Falls back to multiprocessing.
    See: https://github.com/8891689/Secp256k1-CUDA-ecc
    """
    if not quiet:
        print(f"  WARNING: GPU kernels not implemented, using multiprocessing", file=sys.stderr)
    return run_multiprocessing(seeds, algo, workers, quiet)


def get_mode_runner(
    mode: str,
) -> Callable[[list[str], Algorithm, int, bool], list[tuple[str, str, str]]]:
    """Get the runner function for a given mode."""
    runners = {
        "seq": run_sequential,
        "mp": run_multiprocessing,
        "thread": run_threading,
        "hybrid": run_hybrid,
        "gpu": run_gpu,
    }
    return runners[mode]


# =============================================================================
# Trustline Execution Modes
# =============================================================================

def run_trustlines_sequential(
    pairs: list[TrustlinePair], workers: int, quiet: bool, limit: int = 1_000_000
) -> list[TrustlineObjects]:
    """Sequential trustline generation (baseline)."""
    del workers  # Unused
    results = []
    count = len(pairs)
    for i, pair in enumerate(pairs):
        results.append(generate_trustline_objects(pair.addr_a, pair.addr_b, pair.currency, limit))
        if not quiet and (i + 1) % 1000 == 0:
            print(f"  Generated {i + 1}/{count} trustlines...", file=sys.stderr)
    return results


# Module-level function for multiprocessing (must be picklable)
_TRUSTLINE_LIMIT: int = 1_000_000


def _trustline_worker(pair_tuple: tuple[str, str, str]) -> dict:
    """Worker function for trustline generation (returns dict for pickling)."""
    addr_a, addr_b, currency = pair_tuple
    obj = generate_trustline_objects(addr_a, addr_b, currency, _TRUSTLINE_LIMIT)
    return {
        "ripple_state": obj.ripple_state,
        "directory_node_a": obj.directory_node_a,
        "directory_node_b": obj.directory_node_b,
        "rsi": obj.rsi,
    }


def run_trustlines_multiprocessing(
    pairs: list[TrustlinePair], workers: int, quiet: bool, limit: int = 1_000_000
) -> list[TrustlineObjects]:
    """Multiprocessing trustline generation."""
    global _TRUSTLINE_LIMIT
    _TRUSTLINE_LIMIT = limit

    count = len(pairs)
    pair_tuples = [(p.addr_a, p.addr_b, p.currency) for p in pairs]

    with ProcessPoolExecutor(max_workers=workers) as executor:
        results = []
        for i, result_dict in enumerate(executor.map(_trustline_worker, pair_tuples, chunksize=100)):
            results.append(TrustlineObjects(
                ripple_state=result_dict["ripple_state"],
                directory_node_a=result_dict["directory_node_a"],
                directory_node_b=result_dict["directory_node_b"],
                rsi=result_dict["rsi"],
            ))
            if not quiet and (i + 1) % 1000 == 0:
                print(f"  Generated {i + 1}/{count} trustlines...", file=sys.stderr)
    return results


def run_trustlines_threading(
    pairs: list[TrustlinePair], workers: int, quiet: bool, limit: int = 1_000_000
) -> list[TrustlineObjects]:
    """Threading trustline generation (benefits from 3.13t no-GIL)."""
    count = len(pairs)

    def generate(pair: TrustlinePair) -> TrustlineObjects:
        return generate_trustline_objects(pair.addr_a, pair.addr_b, pair.currency, limit)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(generate, pair) for pair in pairs]
        results = []
        for i, future in enumerate(futures):
            results.append(future.result())
            if not quiet and (i + 1) % 1000 == 0:
                print(f"  Generated {i + 1}/{count} trustlines...", file=sys.stderr)
    return results


def get_trustline_mode_runner(
    mode: str,
) -> Callable[[list[TrustlinePair], int, bool, int], list[TrustlineObjects]]:
    """Get the runner function for trustline generation."""
    runners = {
        "seq": run_trustlines_sequential,
        "mp": run_trustlines_multiprocessing,
        "thread": run_trustlines_threading,
        "hybrid": run_trustlines_threading,  # Use threading for hybrid (no benefit from processes here)
        "gpu": run_trustlines_sequential,    # No GPU implementation
    }
    return runners[mode]


# =============================================================================
# Output / Info
# =============================================================================

def format_output(
    results: list[tuple[str, str, str]],
    mode: str,
    workers: int,
    count: int,
    elapsed_derive: float,
    elapsed_seed: float,
    algo: str,
    backend_name: str,
    seeds_from_file: bool = False,
    seeds_file: str | None = None,
    trustline_results: list[TrustlineObjects] | None = None,
    elapsed_trustlines: float | None = None,
    topology: str | None = None,
    currencies: list[str] | None = None,
) -> dict:
    """Format output as JSON structure."""
    meta = {
        "mode": mode,
        "workers": workers,
        "account_count": count,
        "elapsed_accounts_sec": round(elapsed_derive, 3),
        "elapsed_seed_sec": round(elapsed_seed, 3),
        "algorithm": algo,
        "backend": backend_name,
        "account_rate": round(count / elapsed_derive, 1) if elapsed_derive > 0 else 0,
        "seeds_from_file": seeds_from_file,
        "seeds_file": seeds_file,
    }

    if trustline_results is not None and elapsed_trustlines is not None:
        trustline_count = len(trustline_results)
        meta["trustline_count"] = trustline_count
        meta["elapsed_trustlines_sec"] = round(elapsed_trustlines, 3)
        meta["trustline_rate"] = round(trustline_count / elapsed_trustlines, 1) if elapsed_trustlines > 0 else 0
        meta["topology"] = topology
        meta["currencies"] = currencies
        meta["elapsed_total_sec"] = round(elapsed_derive + elapsed_seed + elapsed_trustlines, 3)
    else:
        meta["elapsed_total_sec"] = round(elapsed_derive + elapsed_seed, 3)

    output: dict = {
        "meta": meta,
        "accounts": [
            {"address": addr, "seed": seed, "index": idx}
            for addr, seed, idx in results
        ],
    }

    if trustline_results is not None:
        output["trustlines"] = [
            {"addr_a": t.ripple_state["LowLimit"]["issuer"],
             "addr_b": t.ripple_state["HighLimit"]["issuer"],
             "currency": t.ripple_state["Balance"]["currency"],
             "index": t.rsi}
            for t in trustline_results
        ]

    return output


def print_system_info() -> None:
    """Print system/library information."""
    ed_avail, ed_name = _check_backend_available(Algorithm.ED25519)
    secp_avail, secp_name = _check_backend_available(Algorithm.SECP256K1)

    print("System Info:", file=sys.stderr)
    print(f"  Python: {sys.version.split()[0]}", file=sys.stderr)
    print(f"  CPU cores: {os.cpu_count()}", file=sys.stderr)
    print(f"  ed25519 backend:   {'✓ ' + ed_name if ed_avail else '✗ fallback (slow)'}", file=sys.stderr)
    print(f"  secp256k1 backend: {'✓ ' + secp_name if secp_avail else '✗ fallback (slow)'}", file=sys.stderr)
    print(file=sys.stderr)


# =============================================================================
# Main
# =============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark XRPL account and trustline generation with different parallelization strategies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  seq      Sequential (baseline)
  mp       Multiprocessing (ProcessPoolExecutor)
  thread   Threading (ThreadPoolExecutor, benefits from 3.13t no-GIL)
  hybrid   Processes spawning thread pools
  gpu      GPU acceleration (stub, falls back to mp)

Seed file formats:
  binary (default)  Raw 32-byte seeds with magic header (~3x smaller, faster I/O)
  text              One hex/base58 seed per line (--seeds-text flag)
  --seeds-only      Generate seeds without derivation

Trustline topologies:
  star     All accounts trust account 0 (default, realistic for issued currencies)
  ring     Each account trusts the next
  mesh     All pairs (n*(n-1)/2 trustlines)
  random   Random 30% of possible pairs

Backends (auto-selected):
  ed25519:   PyNaCl (libsodium) ~50,000/sec, fallback ~80/sec
  secp256k1: coincurve (libsecp256k1) ~15,000/sec, fallback ~60/sec

Install native backends:
  pip install pynacl      # for ed25519
  pip install coincurve   # for secp256k1

Examples:
  # Benchmark accounts only
  bench_accounts.py -n 1000 --mode mp

  # Benchmark accounts + trustlines
  bench_accounts.py -n 1000 --trustlines --mode mp

  # Benchmark trustlines with mesh topology
  bench_accounts.py -n 100 --trustlines --topology mesh --mode mp

  # Multiple currencies
  bench_accounts.py -n 1000 --trustlines --currencies USD,EUR,JPY --mode mp
        """,
    )
    # Account generation options
    parser.add_argument("-n", "--count", type=int, help="Number of accounts to generate")
    parser.add_argument("--mode", choices=["seq", "mp", "thread", "hybrid", "gpu"], default="seq")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    parser.add_argument("--algo", choices=["secp256k1", "ed25519"], default="secp256k1")
    parser.add_argument("--output", type=str, metavar="FILE", help="Output JSON file")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")
    parser.add_argument("--info", action="store_true", help="Print system info and exit")
    parser.add_argument("--seeds-file", type=str, metavar="FILE", help="Load seeds from file")
    parser.add_argument("--save-seeds", type=str, metavar="FILE", help="Save seeds to file")
    parser.add_argument("--seeds-only", action="store_true", help="Only generate/save seeds, skip derivation")
    parser.add_argument("--seeds-text", action="store_true",
                        help="Save seeds as text (one per line) instead of binary (default)")

    # Trustline generation options
    parser.add_argument("--trustlines", action="store_true", help="Enable trustline generation benchmark")
    parser.add_argument("--topology", choices=["star", "ring", "mesh", "random"], default="star",
                        help="Trustline topology (default: star)")
    parser.add_argument("--currencies", type=str, default="USD",
                        help="Comma-separated currencies (default: USD)")
    parser.add_argument("--limit", type=int, default=1_000_000,
                        help="Trust limit (default: 1000000)")
    parser.add_argument("--trustlines-only", action="store_true",
                        help="Skip account generation, use --seeds-file for accounts")

    args = parser.parse_args()

    if args.info:
        print_system_info()
        return 0

    if args.count is None and args.seeds_file is None:
        parser.error("-n/--count or --seeds-file is required")

    if args.trustlines_only and not args.seeds_file:
        parser.error("--trustlines-only requires --seeds-file with account data")

    algo = Algorithm.ED25519 if args.algo == "ed25519" else Algorithm.SECP256K1
    backend = get_backend(algo)
    _, backend_name = _check_backend_available(algo)

    # Parse currencies
    currencies = [c.strip() for c in args.currencies.split(",")]
    topology = TrustlineTopology(args.topology)

    # Phase 1: Get seeds
    seed_start = time.perf_counter()
    seeds_from_file = False

    if args.seeds_file:
        try:
            seeds = load_seeds_from_file(args.seeds_file, args.quiet)
            seeds_from_file = True
            if args.count is not None and args.count < len(seeds):
                seeds = seeds[:args.count]
                if not args.quiet:
                    print(f"  Using first {args.count} seeds.", file=sys.stderr)
        except (OSError, ValueError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    else:
        seeds = generate_seeds(args.count, backend, args.quiet)

    seed_elapsed = time.perf_counter() - seed_start
    count = len(seeds)

    if args.save_seeds:
        try:
            save_seeds_to_file(seeds, args.save_seeds, args.quiet, text_format=args.seeds_text)
        except OSError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    if args.seeds_only:
        if not args.save_seeds:
            print("Error: --seeds-only requires --save-seeds", file=sys.stderr)
            return 1
        if not args.quiet:
            print(f"\nSeeds only: {count} seeds generated in {seed_elapsed:.3f}s ({count / seed_elapsed:.0f}/sec)")
        return 0

    if not args.quiet:
        print_system_info()
        seed_source = f"from {args.seeds_file}" if seeds_from_file else "generated"
        print(f"Config: mode={args.mode} | workers={args.workers} | count={count} | "
              f"algo={args.algo} | backend={backend_name}", file=sys.stderr)
        print(f"Seeds: {seed_source}", file=sys.stderr)
        if args.trustlines:
            print(f"Trustlines: topology={args.topology} | currencies={currencies} | "
                  f"limit={args.limit}", file=sys.stderr)
        print(file=sys.stderr)

    # Phase 2: Benchmark account derivation (unless --trustlines-only)
    derive_elapsed = 0.0
    results: list[tuple[str, str, str]] = []

    if not args.trustlines_only:
        if not args.quiet:
            print("  Starting keypair derivation...", file=sys.stderr)

        runner = get_mode_runner(args.mode)
        derive_start = time.perf_counter()
        results = runner(seeds, algo, args.workers, args.quiet)
        derive_elapsed = time.perf_counter() - derive_start
    else:
        # For --trustlines-only, we need to derive addresses from seeds
        # (but we don't benchmark this, just need the addresses)
        if not args.quiet:
            print("  Deriving addresses from seeds (not timed)...", file=sys.stderr)
        encoder = get_address_encoder()
        for seed in seeds:
            public_key, _ = backend.derive_keypair(seed)
            address = encoder.encode(public_key, algo)
            index = account_root_index(address)
            results.append((address, seed, index))

    # Phase 3: Benchmark trustline generation (if enabled)
    trustline_results: list[TrustlineObjects] | None = None
    trustline_elapsed: float | None = None

    if args.trustlines or args.trustlines_only:
        if len(results) < 2:
            print("Error: Need at least 2 accounts for trustlines", file=sys.stderr)
            return 1

        # Generate trustline pairs
        pairs = generate_trustline_pairs(results, topology, currencies)

        if not pairs:
            print("Error: No trustline pairs generated", file=sys.stderr)
            return 1

        if not args.quiet:
            print(f"  Starting trustline generation ({len(pairs)} pairs)...", file=sys.stderr)

        trustline_runner = get_trustline_mode_runner(args.mode)
        trustline_start = time.perf_counter()
        trustline_results = trustline_runner(pairs, args.workers, args.quiet, args.limit)
        trustline_elapsed = time.perf_counter() - trustline_start

    # Output results
    derive_rate = count / derive_elapsed if derive_elapsed > 0 else 0

    print(f"\nResults ({backend_name}):")
    if seeds_from_file:
        print(f"  Seed loading:       {seed_elapsed:.3f}s ({count} seeds)")
    else:
        print(f"  Seed generation:    {seed_elapsed:.3f}s ({count / seed_elapsed:.0f}/sec)")

    if not args.trustlines_only:
        print(f"  Keypair derivation: {derive_elapsed:.3f}s ({derive_rate:.0f}/sec) <- BENCHMARKED")

    if trustline_results is not None and trustline_elapsed is not None:
        trustline_count = len(trustline_results)
        trustline_rate = trustline_count / trustline_elapsed if trustline_elapsed > 0 else 0
        print(f"  Trustline objects:  {trustline_elapsed:.3f}s ({trustline_rate:.0f}/sec) <- BENCHMARKED")
        print(f"    Topology:         {args.topology}")
        print(f"    Pairs:            {trustline_count}")
        print(f"    Currencies:       {currencies}")

    total_elapsed = seed_elapsed + derive_elapsed + (trustline_elapsed or 0)
    print(f"  Total:              {total_elapsed:.3f}s")

    if args.output:
        output_data = format_output(
            results, args.mode, args.workers, count,
            derive_elapsed, seed_elapsed, args.algo, backend_name,
            seeds_from_file=seeds_from_file, seeds_file=args.seeds_file,
            trustline_results=trustline_results, elapsed_trustlines=trustline_elapsed,
            topology=args.topology, currencies=currencies,
        )
        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2)
        print(f"\nResults written to {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
