#!/usr/bin/env python3
"""
Benchmark script for parallel account and trustline generation.

Tests different parallelization strategies for XRPL account generation
and trustline (RippleState + DirectoryNode) object generation,
compatible with Python 3.13t (free-threaded/no-GIL).

Uses the real gl.crypto_backends pipeline so benchmarks measure exactly
the same code path as generate_accounts():
  entropy → key derivation → address encoding → seed encoding

Usage:
    uv run scripts/bench_accounts.py --accounts 100 --mode seq
    uv run scripts/bench_accounts.py --accounts 100 --mode mp --workers 4
    uv run scripts/bench_accounts.py --accounts 100 --mode thread --workers 4
    uv run scripts/bench_accounts.py --accounts 1000 --algo ed25519 --mode mp

    # Benchmark trustline generation
    uv run scripts/bench_accounts.py --accounts 1000 --trustlines --mode mp
    uv run scripts/bench_accounts.py --accounts 100 --trustlines --topology mesh --mode mp
"""

import argparse
import hashlib
import json
import os
import random
import sys
import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum

# Add src directory to path for standalone execution
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gl.crypto_backends import Algorithm, FallbackBackend, backend_info, get_backend
from gl.crypto_backends import CryptoBackend as _CryptoBackend

# =============================================================================
# Trustline Types
# =============================================================================


class TrustlineTopology(Enum):
    """Trustline connection topologies."""

    STAR = "star"  # All accounts trust account 0 (realistic for issued currencies)
    RING = "ring"  # Each account trusts the next
    MESH = "mesh"  # All pairs (n*(n-1)/2 trustlines)
    RANDOM = "random"  # Random pairs


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
# Self-Contained Index Calculations (for trustline benchmarks)
# =============================================================================

NS_TRUST_LINE = b"\x00\x72"  # 'r'
NS_OWNER_DIR = b"\x00\x4f"  # 'O'


def _sha512_half(data: bytes) -> bytes:
    """SHA512-Half: first 32 bytes of SHA512."""
    return hashlib.sha512(data).digest()[:32]


def _currency_to_160(code: str) -> bytes:
    """Convert a currency code to 20-byte representation."""
    code = code.strip()
    if len(code) == 40 and all(c in "0123456789abcdefABCDEF" for c in code):
        return bytes.fromhex(code)
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
    """Compute RippleState ledger index."""
    a1, a2 = _decode_account_id(addr_a), _decode_account_id(addr_b)
    low, high = (a1, a2) if a1 < a2 else (a2, a1)
    preimage = NS_TRUST_LINE + low + high + _currency_to_160(currency)
    return _sha512_half(preimage).hex().upper()


def owner_dir_index(address: str) -> str:
    """Compute owner directory index for an account."""
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
    """Generate RippleState + 2 DirectoryNodes for a trustline."""
    rsi = ripple_state_index(addr_a, addr_b, currency)

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
        "PreviousTxnID": "0" * 64,
        "PreviousTxnLgrSeq": ledger_seq,
        "index": rsi,
    }

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


def generate_trustline_pairs(
    accounts: list[tuple[str, str]],
    topology: TrustlineTopology,
    currencies: list[str],
    random_fraction: float = 0.3,
) -> list[TrustlinePair]:
    """Generate trustline pairs based on topology."""
    if len(accounts) < 2:
        return []

    pairs: list[TrustlinePair] = []
    addresses = [a[0] for a in accounts]
    n = len(addresses)

    for currency in currencies:
        if topology == TrustlineTopology.STAR:
            issuer = addresses[0]
            for i in range(1, n):
                pairs.append(TrustlinePair(issuer, addresses[i], currency))

        elif topology == TrustlineTopology.RING:
            for i in range(n):
                pairs.append(TrustlinePair(addresses[i], addresses[(i + 1) % n], currency))

        elif topology == TrustlineTopology.MESH:
            for i in range(n):
                for j in range(i + 1, n):
                    pairs.append(TrustlinePair(addresses[i], addresses[j], currency))

        elif topology == TrustlineTopology.RANDOM:
            all_pairs = []
            for i in range(n):
                for j in range(i + 1, n):
                    all_pairs.append((addresses[i], addresses[j]))
            num_pairs = max(1, int(len(all_pairs) * random_fraction))
            selected = random.sample(all_pairs, min(num_pairs, len(all_pairs)))
            for addr_a, addr_b in selected:
                pairs.append(TrustlinePair(addr_a, addr_b, currency))

    return pairs


# =============================================================================
# Account Generation (uses real gl.crypto_backends)
# =============================================================================

# Global backend for multiprocessing (initialized per-process)
_BACKEND: _CryptoBackend | None = None


def _init_worker(algo_value: str) -> None:
    """Initialize worker process with the real crypto backend."""
    global _BACKEND
    _BACKEND = get_backend(Algorithm(algo_value))


def _generate_one_account(_: int) -> tuple[str, str]:
    """Generate one account using the global backend (for multiprocessing)."""
    assert _BACKEND is not None
    return _BACKEND.generate_account()


def run_sequential(count: int, algo: Algorithm, workers: int, quiet: bool) -> list[tuple[str, str]]:
    """Sequential account generation (baseline)."""
    del workers
    backend = get_backend(algo)
    results = []
    for i in range(count):
        results.append(backend.generate_account())
        if not quiet and (i + 1) % 1000 == 0:
            print(f"  Generated {i + 1}/{count}...", file=sys.stderr)
    return results


def run_multiprocessing(count: int, algo: Algorithm, workers: int, quiet: bool) -> list[tuple[str, str]]:
    """Multiprocessing using ProcessPoolExecutor."""
    with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker, initargs=(algo.value,)) as executor:
        results = []
        for i, result in enumerate(executor.map(_generate_one_account, range(count), chunksize=100)):
            results.append(result)
            if not quiet and (i + 1) % 1000 == 0:
                print(f"  Generated {i + 1}/{count}...", file=sys.stderr)
    return results


def run_threading(count: int, algo: Algorithm, workers: int, quiet: bool) -> list[tuple[str, str]]:
    """Threading using ThreadPoolExecutor (benefits from 3.13t no-GIL)."""
    backend = get_backend(algo)

    def generate(_: int) -> tuple[str, str]:
        return backend.generate_account()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(generate, i) for i in range(count)]
        results = []
        for i, future in enumerate(futures):
            results.append(future.result())
            if not quiet and (i + 1) % 1000 == 0:
                print(f"  Generated {i + 1}/{count}...", file=sys.stderr)
    return results


def _hybrid_process_batch(args: tuple[int, str, int]) -> list[tuple[str, str]]:
    """Process a batch with a thread pool (module-level for pickling)."""
    batch_count, algo_value, num_threads = args
    backend = get_backend(Algorithm(algo_value))

    def generate(_: int) -> tuple[str, str]:
        return backend.generate_account()

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        return list(executor.map(generate, range(batch_count)))


def run_hybrid(count: int, algo: Algorithm, workers: int, quiet: bool) -> list[tuple[str, str]]:
    """Hybrid mode: processes spawning thread pools."""
    process_workers = max(1, workers // 2)
    thread_workers = max(1, workers // process_workers)

    batch_size = (count + process_workers - 1) // process_workers
    batch_counts = []
    remaining = count
    for _ in range(process_workers):
        n = min(batch_size, remaining)
        if n > 0:
            batch_counts.append(n)
        remaining -= n

    if not quiet:
        print(f"  Hybrid: {len(batch_counts)} processes × {thread_workers} threads", file=sys.stderr)

    with ProcessPoolExecutor(max_workers=len(batch_counts)) as executor:
        args_list = [(bc, algo.value, thread_workers) for bc in batch_counts]
        batch_results = list(executor.map(_hybrid_process_batch, args_list))

    results = []
    for batch in batch_results:
        results.extend(batch)
    return results


def run_gpu(count: int, algo: Algorithm, workers: int, quiet: bool) -> list[tuple[str, str]]:
    """GPU-accelerated ed25519 via CuPy/CUDA."""
    if algo != Algorithm.ED25519:
        if not quiet:
            print("  WARNING: GPU only supports ed25519, falling back to multiprocessing", file=sys.stderr)
        return run_multiprocessing(count, algo, workers, quiet)
    try:
        from gl.gpu_backend import GpuEd25519Backend

        backend = GpuEd25519Backend()
        if not quiet:
            print("  Using GPU (CuPy/CUDA) backend", file=sys.stderr)
        return backend.generate_accounts_batch(count)
    except (ImportError, RuntimeError) as e:
        if not quiet:
            print(f"  WARNING: GPU not available ({e}), falling back to multiprocessing", file=sys.stderr)
        return run_multiprocessing(count, algo, workers, quiet)


def get_mode_runner(
    mode: str,
) -> Callable[[int, Algorithm, int, bool], list[tuple[str, str]]]:
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
    del workers
    results = []
    count = len(pairs)
    for i, pair in enumerate(pairs):
        results.append(generate_trustline_objects(pair.addr_a, pair.addr_b, pair.currency, limit))
        if not quiet and (i + 1) % 1000 == 0:
            print(f"  Generated {i + 1}/{count} trustlines...", file=sys.stderr)
    return results


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
            results.append(
                TrustlineObjects(
                    ripple_state=result_dict["ripple_state"],
                    directory_node_a=result_dict["directory_node_a"],
                    directory_node_b=result_dict["directory_node_b"],
                    rsi=result_dict["rsi"],
                )
            )
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
        "hybrid": run_trustlines_threading,
        "gpu": run_trustlines_sequential,
    }
    return runners[mode]


# =============================================================================
# Output / Info
# =============================================================================


def format_output(
    results: list[tuple[str, str]],
    mode: str,
    workers: int,
    count: int,
    elapsed: float,
    algo: str,
    backend_name: str,
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
        "elapsed_accounts_sec": round(elapsed, 3),
        "algorithm": algo,
        "backend": backend_name,
        "account_rate": round(count / elapsed, 1) if elapsed > 0 else 0,
    }

    if trustline_results is not None and elapsed_trustlines is not None:
        trustline_count = len(trustline_results)
        meta["trustline_count"] = trustline_count
        meta["elapsed_trustlines_sec"] = round(elapsed_trustlines, 3)
        meta["trustline_rate"] = round(trustline_count / elapsed_trustlines, 1) if elapsed_trustlines > 0 else 0
        meta["topology"] = topology
        meta["currencies"] = currencies
        meta["elapsed_total_sec"] = round(elapsed + elapsed_trustlines, 3)
    else:
        meta["elapsed_total_sec"] = round(elapsed, 3)

    output: dict = {
        "meta": meta,
        "accounts": [{"address": addr, "seed": seed} for seed, addr in results],
    }

    if trustline_results is not None:
        output["trustlines"] = [
            {
                "addr_a": t.ripple_state["LowLimit"]["issuer"],
                "addr_b": t.ripple_state["HighLimit"]["issuer"],
                "currency": t.ripple_state["Balance"]["currency"],
                "index": t.rsi,
            }
            for t in trustline_results
        ]

    return output


def print_system_info() -> None:
    """Print system/library information."""
    ed_native, ed_name = backend_info(Algorithm.ED25519)
    secp_native, secp_name = backend_info(Algorithm.SECP256K1)

    print("System Info:", file=sys.stderr)
    print(f"  Python: {sys.version.split()[0]}", file=sys.stderr)
    print(f"  CPU cores: {os.cpu_count()}", file=sys.stderr)
    print(f"  ed25519 backend:   {'✓ ' + ed_name if ed_native else '✗ fallback (slow)'}", file=sys.stderr)
    print(f"  secp256k1 backend: {'✓ ' + secp_name if secp_native else '✗ fallback (slow)'}", file=sys.stderr)
    print(file=sys.stderr)


# =============================================================================
# Backend Comparison
# =============================================================================


@dataclass
class _BenchResult:
    """Result of a single backend benchmark run."""

    algo: str
    backend: str
    is_native: bool
    count: int
    elapsed: float
    rate: float


def _bench_backend(backend: _CryptoBackend, count: int, label: str, quiet: bool) -> _BenchResult:
    """Benchmark a single backend."""
    if not quiet:
        print(f"  {label}...", file=sys.stderr)
    start = time.perf_counter()
    for _ in range(count):
        backend.generate_account()
    elapsed = time.perf_counter() - start
    rate = count / elapsed if elapsed > 0 else 0
    is_native = not isinstance(backend, FallbackBackend)
    return _BenchResult(
        algo=backend.algorithm.value,
        backend=label.split("(")[1].rstrip(")") if "(" in label else label,
        is_native=is_native,
        count=count,
        elapsed=elapsed,
        rate=rate,
    )


def run_compare(count: int, quiet: bool) -> list[_BenchResult]:
    """Benchmark all available backends and return results."""
    results: list[_BenchResult] = []

    # ed25519 native (PyNaCl)
    try:
        from gl.crypto_backends import NativeEd25519Backend

        backend = NativeEd25519Backend()
        results.append(_bench_backend(backend, count, "ed25519 (pynacl)", quiet))
    except ImportError:
        if not quiet:
            print("  ed25519 native: not available (pip install pynacl)", file=sys.stderr)

    # ed25519 fallback (xrpl-py)
    results.append(_bench_backend(FallbackBackend(Algorithm.ED25519), count, "ed25519 (xrpl-py)", quiet))

    # secp256k1 native (coincurve)
    try:
        from gl.crypto_backends import NativeSecp256k1Backend

        backend = NativeSecp256k1Backend()
        results.append(_bench_backend(backend, count, "secp256k1 (coincurve)", quiet))
    except ImportError:
        if not quiet:
            print("  secp256k1 native: not available (pip install coincurve)", file=sys.stderr)

    # secp256k1 fallback (xrpl-py)
    results.append(_bench_backend(FallbackBackend(Algorithm.SECP256K1), count, "secp256k1 (xrpl-py)", quiet))

    return results


def print_compare_table(results: list[_BenchResult]) -> None:
    """Print a formatted comparison table."""
    # Header
    print()
    print(f"{'Backend':<26} {'Type':<10} {'Count':>7} {'Time (s)':>10} {'Rate (/s)':>12} {'Speedup':>9}")
    print("─" * 78)

    # Group by algorithm to compute speedups
    by_algo: dict[str, list[_BenchResult]] = {}
    for r in results:
        by_algo.setdefault(r.algo, []).append(r)

    for algo, algo_results in by_algo.items():
        # Baseline is the xrpl-py (fallback) rate
        fallback_rate = next((r.rate for r in algo_results if not r.is_native), 0)
        for r in algo_results:
            speedup = f"{r.rate / fallback_rate:.1f}x" if fallback_rate > 0 else "—"
            tag = "native" if r.is_native else "fallback"
            print(
                f"  {r.algo:<10} {r.backend:<13} {tag:<10}"
                f" {r.count:>7,} {r.elapsed:>10.3f} {r.rate:>11,.0f} {speedup:>9}"
            )
        if algo != list(by_algo)[-1]:
            print()

    # Summary
    print("─" * 78)
    if len(by_algo) > 1:
        natives = [r for r in results if r.is_native]
        fallbacks = [r for r in results if not r.is_native]
        if natives and fallbacks:
            best_native = max(natives, key=lambda r: r.rate)
            worst_fallback = min(fallbacks, key=lambda r: r.rate)
            print(f"  Fastest: {best_native.algo} ({best_native.backend}) at {best_native.rate:,.0f}/sec")
            print(f"  Slowest: {worst_fallback.algo} ({worst_fallback.backend}) at {worst_fallback.rate:,.0f}/sec")
            overall = best_native.rate / worst_fallback.rate if worst_fallback.rate > 0 else 0
            print(f"  Overall speedup (best native vs worst fallback): {overall:.0f}x")
    print()


# =============================================================================
# Main
# =============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark XRPL account and trustline generation with different parallelization strategies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  bench_accounts.py --compare                           # compare all backends (500 accounts)
  bench_accounts.py --compare --accounts 2000           # compare with 2000 accounts
  bench_accounts.py --accounts 1000 --mode mp
  bench_accounts.py --accounts 1000 --trustlines --mode mp
  bench_accounts.py --accounts 100 --trustlines --topology mesh --mode mp
        """,
    )
    parser.add_argument("--accounts", type=int, help="Number of accounts to generate (required unless --info)")
    parser.add_argument(
        "--mode",
        choices=["seq", "mp", "thread", "hybrid", "gpu"],
        default="seq",
        help=(
            "Parallelization strategy for account generation. "
            "seq = single-threaded baseline; "
            "mp = multiprocessing (one process per worker, best for CPU-bound crypto); "
            "thread = multithreaded (benefits from Python 3.13t free-threaded/no-GIL builds); "
            "hybrid = process pool where each process spawns a thread pool; "
            "gpu = GPU-accelerated EC ops (stub, falls back to mp). "
            "(default: seq)"
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=os.cpu_count() or 4,
        help=(
            "Number of parallel workers (processes or threads, depending on --mode). "
            "Ignored when mode is seq. (default: CPU core count, currently %(default)s)"
        ),
    )
    parser.add_argument(
        "--algo",
        choices=["secp256k1", "ed25519"],
        default="secp256k1",
        help=(
            "Cryptographic algorithm for account generation. "
            "ed25519 is faster with PyNaCl; secp256k1 is the traditional XRPL algorithm. "
            "(default: secp256k1)"
        ),
    )
    parser.add_argument(
        "--output",
        type=str,
        metavar="FILE",
        help="Write results (accounts, trustlines, timing metadata) to a JSON file",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output (only print final results)")
    parser.add_argument(
        "--info", action="store_true", help="Print detected backends, Python version, and CPU count, then exit"
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help=(
            "Run all available backends (native + fallback for each algorithm) "
            "and print a comparison table with speedups. Uses sequential mode."
        ),
    )

    # Trustline generation options
    parser.add_argument(
        "--trustlines",
        action="store_true",
        help=(
            "Also benchmark trustline (RippleState + DirectoryNode) object generation "
            "after accounts are created. Pairs are determined by --topology."
        ),
    )
    parser.add_argument(
        "--topology",
        choices=["star", "ring", "mesh", "random"],
        default="star",
        help=(
            "How accounts are paired for trustlines. "
            "star = all trust account 0 (realistic issuer model); "
            "ring = each trusts the next, forming a loop; "
            "mesh = every pair connected (n*(n-1)/2 trustlines); "
            "random = random 30%% of all possible pairs. "
            "(default: star)"
        ),
    )
    parser.add_argument(
        "--currencies",
        type=str,
        default="USD",
        help=(
            "Comma-separated currency codes. A trustline is created for each "
            "currency per account pair, so 3 currencies triples the trustline count. "
            "(default: USD)"
        ),
    )
    parser.add_argument(
        "--limit", type=int, default=1_000_000, help="Trust limit set on each trustline (default: 1000000)"
    )

    args = parser.parse_args()

    if args.info:
        print_system_info()
        return 0

    if args.accounts is None and not args.compare:
        parser.print_help()
        return 0

    if args.compare:
        count = args.accounts or 500
        if not args.quiet:
            print_system_info()
            print(f"Comparing all backends with {count} accounts each...\n", file=sys.stderr)
        results = run_compare(count, args.quiet)
        print_compare_table(results)
        if args.output:
            output_data = {
                "meta": {"mode": "compare", "count": count},
                "results": [
                    {
                        "algo": r.algo,
                        "backend": r.backend,
                        "is_native": r.is_native,
                        "count": r.count,
                        "elapsed_sec": round(r.elapsed, 3),
                        "rate_per_sec": round(r.rate, 1),
                    }
                    for r in results
                ],
            }
            with open(args.output, "w") as f:
                json.dump(output_data, f, indent=2)
            print(f"Results written to {args.output}")
        return 0

    algo = Algorithm.ED25519 if args.algo == "ed25519" else Algorithm.SECP256K1
    _, backend_name = backend_info(algo)

    # Parse currencies
    currencies = [c.strip() for c in args.currencies.split(",")]
    topology = TrustlineTopology(args.topology)

    if not args.quiet:
        print_system_info()
        print(
            f"Config: mode={args.mode} | workers={args.workers} | count={args.accounts} | "
            f"algo={args.algo} | backend={backend_name}",
            file=sys.stderr,
        )
        if args.trustlines:
            print(
                f"Trustlines: topology={args.topology} | currencies={currencies} | limit={args.limit}", file=sys.stderr
            )
        print(file=sys.stderr)

    # Phase 1: Benchmark account generation (entropy → seed + address)
    if not args.quiet:
        print("  Starting account generation...", file=sys.stderr)

    runner = get_mode_runner(args.mode)
    gen_start = time.perf_counter()
    results = runner(args.accounts, algo, args.workers, args.quiet)
    gen_elapsed = time.perf_counter() - gen_start

    count = len(results)

    # Phase 2: Benchmark trustline generation (if enabled)
    trustline_results: list[TrustlineObjects] | None = None
    trustline_elapsed: float | None = None

    if args.trustlines:
        if count < 2:
            print("Error: Need at least 2 accounts for trustlines", file=sys.stderr)
            return 1

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
    gen_rate = count / gen_elapsed if gen_elapsed > 0 else 0

    print(f"\nResults ({backend_name}):")
    print(f"  Account generation: {gen_elapsed:.3f}s ({gen_rate:,.0f}/sec)")

    if trustline_results is not None and trustline_elapsed is not None:
        trustline_count = len(trustline_results)
        trustline_rate = trustline_count / trustline_elapsed if trustline_elapsed > 0 else 0
        print(f"  Trustline objects:  {trustline_elapsed:.3f}s ({trustline_rate:,.0f}/sec)")
        print(f"    Topology:         {args.topology}")
        print(f"    Pairs:            {trustline_count}")
        print(f"    Currencies:       {currencies}")

    total_elapsed = gen_elapsed + (trustline_elapsed or 0)
    print(f"  Total:              {total_elapsed:.3f}s")

    if args.output:
        output_data = format_output(
            results,
            args.mode,
            args.workers,
            count,
            gen_elapsed,
            args.algo,
            backend_name,
            trustline_results=trustline_results,
            elapsed_trustlines=trustline_elapsed,
            topology=args.topology,
            currencies=currencies,
        )
        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2)
        print(f"\nResults written to {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
