"""Tests for generate_ledger.crypto_backends — fast crypto backend selection and correctness."""

import pytest

from generate_ledger.crypto_backends import (
    Algorithm,
    FallbackBackend,
    NativeEd25519Backend,
    NativeSecp256k1Backend,
    backend_info,
    get_backend,
    hex_to_base58_seed,
)

try:
    import nacl  # noqa: F401

    _HAS_PYNACL = True
except ImportError:
    _HAS_PYNACL = False

try:
    import coincurve  # noqa: F401

    _HAS_COINCURVE = True
except ImportError:
    _HAS_COINCURVE = False


class TestAlgorithm:
    def test_ed25519_value(self):
        assert Algorithm.ED25519.value == "ed25519"

    def test_secp256k1_value(self):
        assert Algorithm.SECP256K1.value == "secp256k1"

    def test_from_string(self):
        assert Algorithm("ed25519") == Algorithm.ED25519
        assert Algorithm("secp256k1") == Algorithm.SECP256K1


class TestHexToBase58Seed:
    def test_produces_s_prefix(self):
        hex_seed = "00" * 16  # 16 zero bytes
        result = hex_to_base58_seed(hex_seed)
        assert result.startswith("s")

    def test_length(self):
        hex_seed = "ab" * 16
        result = hex_to_base58_seed(hex_seed)
        assert 27 <= len(result) <= 30  # typical base58 seed length

    def test_deterministic(self):
        hex_seed = "deadbeef" * 4
        assert hex_to_base58_seed(hex_seed) == hex_to_base58_seed(hex_seed)

    def test_different_seeds_differ(self):
        s1 = hex_to_base58_seed("00" * 16)
        s2 = hex_to_base58_seed("ff" * 16)
        assert s1 != s2


@pytest.mark.skipif(not _HAS_PYNACL, reason="PyNaCl not installed")
class TestNativeEd25519Backend:
    def test_algorithm(self):
        backend = NativeEd25519Backend()
        assert backend.algorithm == Algorithm.ED25519

    def test_generate_account(self):
        backend = NativeEd25519Backend()
        seed, address = backend.generate_account()
        assert seed.startswith("s")
        assert address.startswith("r")

    def test_unique_accounts(self):
        backend = NativeEd25519Backend()
        accounts = [backend.generate_account() for _ in range(10)]
        addresses = {addr for _, addr in accounts}
        assert len(addresses) == 10

    def test_wallet_importable(self):
        """Critical: native-generated seeds must work with xrpl-py Wallet."""
        from xrpl import CryptoAlgorithm
        from xrpl.wallet import Wallet

        backend = NativeEd25519Backend()
        for _ in range(5):
            seed, address = backend.generate_account()
            wallet = Wallet.from_seed(seed, algorithm=CryptoAlgorithm.ED25519)
            assert wallet.address == address


class TestFallbackBackend:
    def test_ed25519(self):
        backend = FallbackBackend(Algorithm.ED25519)
        assert backend.algorithm == Algorithm.ED25519
        seed, address = backend.generate_account()
        assert seed.startswith("s")
        assert address.startswith("r")

    def test_secp256k1(self):
        backend = FallbackBackend(Algorithm.SECP256K1)
        assert backend.algorithm == Algorithm.SECP256K1
        seed, address = backend.generate_account()
        assert seed.startswith("s")
        assert address.startswith("r")


@pytest.mark.skipif(not _HAS_COINCURVE, reason="coincurve not installed")
class TestNativeSecp256k1Backend:
    def test_algorithm(self):
        backend = NativeSecp256k1Backend()
        assert backend.algorithm == Algorithm.SECP256K1

    def test_generate_account(self):
        backend = NativeSecp256k1Backend()
        seed, address = backend.generate_account()
        assert seed.startswith("s")
        assert not seed.startswith("sEd")
        assert address.startswith("r")

    def test_unique_accounts(self):
        backend = NativeSecp256k1Backend()
        accounts = [backend.generate_account() for _ in range(10)]
        addresses = {addr for _, addr in accounts}
        assert len(addresses) == 10

    def test_wallet_importable(self):
        """Critical: native-generated seeds must produce same address via xrpl-py."""
        from xrpl import CryptoAlgorithm
        from xrpl.wallet import Wallet

        backend = NativeSecp256k1Backend()
        for _ in range(5):
            seed, address = backend.generate_account()
            wallet = Wallet.from_seed(seed, algorithm=CryptoAlgorithm.SECP256K1)
            assert wallet.address == address


class TestGetBackend:
    @pytest.mark.skipif(not _HAS_PYNACL, reason="PyNaCl not installed")
    def test_ed25519_returns_native(self):
        backend = get_backend(Algorithm.ED25519)
        assert isinstance(backend, NativeEd25519Backend)

    @pytest.mark.skipif(not _HAS_COINCURVE, reason="coincurve not installed")
    def test_secp256k1_returns_native(self):
        backend = get_backend(Algorithm.SECP256K1)
        assert isinstance(backend, NativeSecp256k1Backend)

    def test_ed25519_returns_fallback_without_native(self):
        backend = get_backend(Algorithm.ED25519)
        assert backend is not None

    def test_secp256k1_returns_fallback_without_native(self):
        backend = get_backend(Algorithm.SECP256K1)
        assert backend is not None


class TestBackendInfo:
    @pytest.mark.skipif(not _HAS_PYNACL, reason="PyNaCl not installed")
    def test_ed25519_native(self):
        is_native, name = backend_info(Algorithm.ED25519)
        assert is_native is True
        assert name == "pynacl"

    @pytest.mark.skipif(not _HAS_COINCURVE, reason="coincurve not installed")
    def test_secp256k1_native(self):
        is_native, name = backend_info(Algorithm.SECP256K1)
        assert is_native is True
        assert name == "coincurve"
