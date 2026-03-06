"""Tests for gl.gpu_backend — GPU-accelerated ed25519 account generation."""

import pytest

# Skip entire module if CuPy or CUDA toolkit is unavailable.
# We must instantiate — import alone succeeds even without CUDA toolkit,
# but RawModule compilation fails at __init__ time.
try:
    from generate_ledger.gpu_backend import GpuEd25519Backend

    GpuEd25519Backend()
    _GPU_AVAILABLE = True
except (ImportError, RuntimeError, Exception):
    _GPU_AVAILABLE = False

pytestmark = pytest.mark.skipif(not _GPU_AVAILABLE, reason="CuPy/CUDA not available")


class TestGpuEd25519Backend:
    def test_algorithm(self):
        backend = GpuEd25519Backend()
        assert backend.algorithm.value == "ed25519"

    def test_generate_account(self):
        backend = GpuEd25519Backend()
        seed, address = backend.generate_account()
        assert seed.startswith("sEd")
        assert address.startswith("r")

    def test_unique_accounts(self):
        backend = GpuEd25519Backend()
        accounts = [backend.generate_account() for _ in range(10)]
        addresses = {addr for _, addr in accounts}
        assert len(addresses) == 10

    def test_wallet_importable(self):
        """Critical: GPU-generated seeds must produce the same address via xrpl-py Wallet."""
        from xrpl import CryptoAlgorithm
        from xrpl.wallet import Wallet

        backend = GpuEd25519Backend()
        for _ in range(10):
            seed, address = backend.generate_account()
            wallet = Wallet.from_seed(seed, algorithm=CryptoAlgorithm.ED25519)
            assert wallet.address == address

    def test_ed25519_seeds_start_with_sEd(self):
        backend = GpuEd25519Backend()
        for _ in range(5):
            seed, _ = backend.generate_account()
            assert seed.startswith("sEd"), f"Expected sEd prefix, got {seed[:4]}"


class TestGpuBatchGeneration:
    def test_batch_size(self):
        backend = GpuEd25519Backend()
        results = backend.generate_accounts_batch(100)
        assert len(results) == 100

    def test_batch_unique(self):
        backend = GpuEd25519Backend()
        results = backend.generate_accounts_batch(100)
        addresses = {addr for _, addr in results}
        assert len(addresses) == 100

    def test_batch_wallet_importable(self):
        """Every account in a batch must be importable via xrpl-py."""
        from xrpl import CryptoAlgorithm
        from xrpl.wallet import Wallet

        backend = GpuEd25519Backend()
        results = backend.generate_accounts_batch(50)
        for seed, address in results:
            wallet = Wallet.from_seed(seed, algorithm=CryptoAlgorithm.ED25519)
            assert wallet.address == address

    def test_batch_of_one(self):
        backend = GpuEd25519Backend()
        results = backend.generate_accounts_batch(1)
        assert len(results) == 1
        seed, addr = results[0]
        assert seed.startswith("sEd")
        assert addr.startswith("r")
