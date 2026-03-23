"""GPU-accelerated ed25519 account generation using CuPy/CUDA.

Implements the full XRPL ed25519 account derivation pipeline on GPU:
  entropy (16B) -> SHA-512 -> ed25519 seed (32B) -> SHA-512 -> scalar (clamped)
  -> scalar * BasePoint -> public key (32B) -> SHA-256 -> RIPEMD-160 -> account ID (20B)
  -> base58check encoding -> ledger index computation

CUDA kernel source lives in cuda/ed25519_accounts.cu (not inline Python strings).

Performance (RTX 5090):
    GpuEd25519Backend:          ~580,000 accounts+indices/sec (batch)
    NativeEd25519Backend:        ~26,000 accounts/sec (sequential)
"""

import os
from pathlib import Path

import numpy as np

from generate_ledger.crypto_backends import Algorithm, CryptoBackend

_CUDA_DIR = Path(__file__).parent / "cuda"


def _ensure_cuda_path() -> None:
    """Auto-detect CUDA_PATH from the nvidia-cuda-nvcc pip wheel if not already set."""
    if os.environ.get("CUDA_PATH"):
        return
    try:
        import nvidia.cuda_nvcc  # noqa: PLC0415

        nvcc_path = nvidia.cuda_nvcc.__path__[0]
        os.environ["CUDA_PATH"] = nvcc_path
    except (ImportError, IndexError):
        pass


def _load_cuda_source() -> str:
    """Load CUDA kernel source from the .cu file."""
    cu_path = _CUDA_DIR / "ed25519_accounts.cu"
    return cu_path.read_text()


class GpuEd25519Backend(CryptoBackend):
    """Ed25519 account generation on GPU via CuPy/CUDA.

    Generates accounts in batches for maximum GPU utilization.
    Single-account generation is supported but less efficient.
    """

    def __init__(self) -> None:
        _ensure_cuda_path()
        import cupy as cp  # noqa: PLC0415

        self._cp = cp
        # The ed25519 kernel has deep call stacks (~2KB per thread).
        # Increase the CUDA stack limit from the default 1024 bytes.
        cp.cuda.runtime.deviceSetLimit(0x00, 16384)  # cudaLimitStackSize = 16KB
        # Compile CUDA module (cached by CuPy after first run)
        cuda_source = _load_cuda_source()
        self._module = cp.RawModule(code=cuda_source, options=("--std=c++17",))
        self._kernel = self._module.get_function("generate_ed25519_accounts")

    @property
    def algorithm(self) -> Algorithm:
        return Algorithm.ED25519

    def generate_account(self) -> tuple[str, str]:
        """Generate a single account. For bulk generation, use generate_accounts_batch()."""
        results = self.generate_accounts_batch(1)
        return results[0]

    def _launch_chunk(
        self,
        entropy_np: np.ndarray,
        n: int,
    ) -> tuple:
        """Launch one GPU chunk. Returns host arrays for seeds, addrs, account_ids, indices."""
        cp = self._cp

        d_entropy = cp.asarray(entropy_np)
        d_seeds = cp.zeros((n, 40), dtype=cp.uint8)
        d_addrs = cp.zeros((n, 40), dtype=cp.uint8)
        d_acct_ids = cp.zeros((n, 20), dtype=cp.uint8)
        d_acct_root_idx = cp.zeros((n, 64), dtype=cp.uint8)
        d_owner_dir_idx = cp.zeros((n, 64), dtype=cp.uint8)

        block_size = 64
        grid_size = (n + block_size - 1) // block_size
        self._kernel(
            (grid_size,),
            (block_size,),
            (d_entropy, d_seeds, d_addrs, d_acct_ids, d_acct_root_idx, d_owner_dir_idx, np.int32(n)),
        )

        return (
            d_seeds.get(),
            d_addrs.get(),
            d_acct_ids.get(),
            d_acct_root_idx.get(),
            d_owner_dir_idx.get(),
        )

    @staticmethod
    def _decode_chunk(
        seed_raw: np.ndarray,
        addr_raw: np.ndarray,
        acct_id_raw: np.ndarray,
        acct_root_raw: np.ndarray,
        owner_dir_raw: np.ndarray,
    ) -> list[tuple[str, str, bytes, str, str]]:
        """Decode GPU output buffers to Python objects."""
        n = seed_raw.shape[0]
        seed_lens = np.argmin(seed_raw, axis=1)
        addr_lens = np.argmin(addr_raw, axis=1)
        seed_flat = seed_raw.tobytes()
        addr_flat = addr_raw.tobytes()
        acct_root_flat = acct_root_raw.tobytes()
        owner_dir_flat = owner_dir_raw.tobytes()
        results: list[tuple[str, str, bytes, str, str]] = []
        for i in range(n):
            si = i * 40
            results.append(
                (
                    seed_flat[si : si + seed_lens[i]].decode("ascii"),
                    addr_flat[si : si + addr_lens[i]].decode("ascii"),
                    acct_id_raw[i].tobytes(),
                    acct_root_flat[i * 64 : (i + 1) * 64].decode("ascii"),
                    owner_dir_flat[i * 64 : (i + 1) * 64].decode("ascii"),
                )
            )
        return results

    def generate_accounts_batch(self, n: int) -> list[tuple[str, str]]:
        """Generate n accounts (CryptoBackend interface: returns (seed, address) tuples)."""
        return [(seed, addr) for seed, addr, *_ in self._generate_full_batch(n)]

    def generate_accounts_full(self, n: int) -> list[tuple[str, str, bytes, str, str]]:
        """Generate n accounts with precomputed indices.

        Returns list of (seed, address, account_id_bytes, account_root_index_hex,
        owner_dir_index_hex). The raw account_id and indices are computed on GPU,
        avoiding the base58 round-trip that the CPU pipeline would need in ledger_builder.
        """
        return self._generate_full_batch(n)

    def _generate_full_batch(self, n: int) -> list[tuple[str, str, bytes, str, str]]:
        """Core batch generation with pipelining for large batches."""
        chunk_size = 50_000
        if n <= chunk_size:
            entropy_np = np.frombuffer(os.urandom(n * 16), dtype=np.uint8).reshape(n, 16)
            return self._decode_chunk(*self._launch_chunk(entropy_np, n))

        from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415

        results: list[tuple[str, str, bytes, str, str]] = []
        all_entropy = np.frombuffer(os.urandom(n * 16), dtype=np.uint8).reshape(n, 16)

        with ThreadPoolExecutor(max_workers=1) as decode_pool:
            pending_future = None
            offset = 0
            remaining = n
            while remaining > 0:
                chunk_n = min(chunk_size, remaining)
                chunk_data = self._launch_chunk(all_entropy[offset : offset + chunk_n], chunk_n)

                if pending_future is not None:
                    results.extend(pending_future.result())

                pending_future = decode_pool.submit(self._decode_chunk, *chunk_data)
                offset += chunk_n
                remaining -= chunk_n

            if pending_future is not None:
                results.extend(pending_future.result())

        return results
