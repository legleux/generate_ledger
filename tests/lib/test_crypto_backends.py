"""Tests for gl.crypto_backends — fast crypto backend selection and correctness."""
import pytest
from gl.crypto_backends import (
    Algorithm,
    CryptoBackend,
    FallbackBackend,
    NativeEd25519Backend,
    backend_info,
    get_backend,
    hex_to_base58_seed,
)


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


class TestGetBackend:
    def test_ed25519_returns_native(self):
        backend = get_backend(Algorithm.ED25519)
        assert isinstance(backend, NativeEd25519Backend)

    def test_secp256k1_returns_fallback(self):
        backend = get_backend(Algorithm.SECP256K1)
        assert isinstance(backend, FallbackBackend)


class TestBackendInfo:
    def test_ed25519_native(self):
        is_native, name = backend_info(Algorithm.ED25519)
        assert is_native is True
        assert name == "pynacl"

    def test_secp256k1_fallback(self):
        is_native, name = backend_info(Algorithm.SECP256K1)
        assert is_native is False
        assert name == "xrpl-py"
