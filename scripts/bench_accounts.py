#!/usr/bin/env python3
"""Benchmark script for generate_ledger account, trustline, and pipeline generation.

Benchmarks the actual library functions with proper
GPU warmup separation, multiple iteration support and comparison tables.

Usage:
    uv run scripts/bench_accounts.py --accounts 1000
    uv run scripts/bench_accounts.py --accounts 1000 --gpu
    uv run scripts/bench_accounts.py --accounts 1000 --target trustlines
    uv run scripts/bench_accounts.py --accounts 10 --target pipeline
    uv run scripts/bench_accounts.py --compare
    uv run scripts/bench_accounts.py --compare --accounts 2000
    uv run scripts/bench_accounts.py --accounts 1000 --iterations 5
    uv run scripts/bench_accounts.py --info
"""

import os
import sys
import time
from dataclasses import dataclass

# Add src directory to path for standalone execution
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@dataclass
class BenchResult:
    """Result of a single benchmark run."""

    label: str
    count: int
    warmup_sec: float
    elapsed_sec: float
    iterations: int
    stddev_sec: float

    @property
    def rate(self) -> float:
        """Items per second (excludes warmup)."""
        return self.count / self.elapsed_sec if self.elapsed_sec > 0 else 0.0


def get_system_info() -> dict:
    """Collect system and backend information."""
    info = {
        "python_version": sys.version.split()[0],
        "cpu_count": os.cpu_count(),
    }
    return info


def format_json(results: list[BenchResult]) -> dict:
    """Format benchmark results as a JSON-serializable dict."""
    return {
        "system": get_system_info(),
        "results": [
            {
                "label": r.label,
                "count": r.count,
                "warmup_sec": round(r.warmup_sec, 3),
                "elapsed_sec": round(r.elapsed_sec, 3),
                "rate": round(r.rate, 1),
                "iterations": r.iterations,
                "stddev_sec": round(r.stddev_sec, 3),
            }
            for r in results
        ],
    }


def format_table(results: list[BenchResult]) -> str:
    """Format benchmark results as a human-readable table."""
    header = f"{'Label':<30} {'Count':>7} {'Time (s)':>10} {'Rate (/s)':>12} {'Warmup (s)':>10}"
    separator = "-" * len(header)
    lines = [header, separator]
    for r in results:
        lines.append(f"  {r.label:<28} {r.count:>7,} {r.elapsed_sec:>10.3f} {r.rate:>11,.0f} {r.warmup_sec:>10.3f}")
    return "\n".join(lines)


# =============================================================================
# Iteration helper
# =============================================================================


def _run_iterations(fn, iterations: int) -> tuple[float, float]:
    """Run fn() `iterations` times. Returns (mean_elapsed, stddev)."""
    import statistics

    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        times.append(time.perf_counter() - start)

    mean = statistics.mean(times)
    stddev = statistics.stdev(times) if len(times) > 1 else 0.0
    return mean, stddev


# =============================================================================
# Runner functions — each benchmarks a real library function
# =============================================================================


def run_accounts(count: int, algo: str = "ed25519", use_gpu: bool = False, iterations: int = 1) -> BenchResult:
    """Benchmark generate_accounts() — the main library entry point."""
    from generate_ledger.accounts import AccountConfig, generate_accounts
    from generate_ledger.crypto_backends import Algorithm, backend_info

    cfg = AccountConfig(num_accounts=count, algo=algo, use_gpu=use_gpu)
    _, backend_name = backend_info(Algorithm(algo), use_gpu=use_gpu)

    result_holder = []

    def bench():
        result_holder.clear()
        result_holder.extend(generate_accounts(cfg, use_gpu=use_gpu))

    mean, stddev = _run_iterations(bench, iterations)

    return BenchResult(
        label=f"{algo} ({backend_name})",
        count=len(result_holder),
        warmup_sec=0.0,
        elapsed_sec=mean,
        iterations=iterations,
        stddev_sec=stddev,
    )


def run_trustlines(
    accounts: list | None = None,
    count: int = 0,
    algo: str = "ed25519",
    currency: str = "USD",
    limit: int = 1_000_000,
) -> BenchResult:
    """Benchmark trustline generation using library's generate_trustline_objects_fast()."""
    from generate_ledger.accounts import AccountConfig, generate_accounts
    from generate_ledger.trustlines import generate_trustline_objects_fast

    if accounts is None:
        cfg = AccountConfig(num_accounts=max(count, 10), algo=algo)
        accounts = generate_accounts(cfg)

    # Star topology: all accounts trust account[0]
    issuer = accounts[0]
    start = time.perf_counter()
    trustline_count = 0
    for acct in accounts[1:]:
        generate_trustline_objects_fast(issuer, acct, currency, limit)
        trustline_count += 1
    elapsed = time.perf_counter() - start

    return BenchResult(
        label=f"trustlines (star, {currency})",
        count=trustline_count,
        warmup_sec=0.0,
        elapsed_sec=elapsed,
        iterations=1,
        stddev_sec=0.0,
    )


def run_pipeline(num_accounts: int = 10) -> BenchResult:
    """Benchmark gen_ledger_state() — the full ledger generation pipeline."""
    from generate_ledger.ledger import LedgerConfig, gen_ledger_state

    cfg = LedgerConfig(account_cfg={"num_accounts": num_accounts})

    start = time.perf_counter()
    result = gen_ledger_state(cfg, write_accounts=False)
    elapsed = time.perf_counter() - start

    object_count = len(result.get("ledger", {}).get("accountState", []))

    return BenchResult(
        label="pipeline (gen_ledger_state)",
        count=object_count,
        warmup_sec=0.0,
        elapsed_sec=elapsed,
        iterations=1,
        stddev_sec=0.0,
    )


def warmup_gpu() -> float:
    """Run a small GPU batch to trigger CUDA kernel compilation. Returns warmup time in seconds."""
    from generate_ledger.gpu_backend import GpuEd25519Backend

    backend = GpuEd25519Backend()
    start = time.perf_counter()
    backend.generate_accounts_batch(1)
    elapsed = time.perf_counter() - start
    return elapsed


def run_gpu_batch(count: int) -> BenchResult:
    """Benchmark GpuEd25519Backend.generate_accounts_batch() (assumes GPU already warmed up)."""
    from generate_ledger.gpu_backend import GpuEd25519Backend

    backend = GpuEd25519Backend()
    start = time.perf_counter()
    results = backend.generate_accounts_batch(count)
    elapsed = time.perf_counter() - start

    return BenchResult(
        label="ed25519 GPU (batch)",
        count=len(results),
        warmup_sec=0.0,
        elapsed_sec=elapsed,
        iterations=1,
        stddev_sec=0.0,
    )


def run_gpu_full(count: int) -> BenchResult:
    """Benchmark GpuEd25519Backend.generate_accounts_full() (assumes GPU already warmed up)."""
    from generate_ledger.gpu_backend import GpuEd25519Backend

    backend = GpuEd25519Backend()
    start = time.perf_counter()
    results = backend.generate_accounts_full(count)
    elapsed = time.perf_counter() - start

    return BenchResult(
        label="ed25519 GPU (full+indices)",
        count=len(results),
        warmup_sec=0.0,
        elapsed_sec=elapsed,
        iterations=1,
        stddev_sec=0.0,
    )


def run_compare(count: int = 500) -> list[BenchResult]:
    """Benchmark all available backends and return results."""
    from generate_ledger.accounts import AccountConfig, generate_accounts
    from generate_ledger.crypto_backends import Algorithm, FallbackBackend, backend_info

    results: list[BenchResult] = []

    for algo_str in ("ed25519", "secp256k1"):
        algo = Algorithm(algo_str)

        # Native backend
        is_native, native_name = backend_info(algo)
        if is_native:
            cfg = AccountConfig(num_accounts=count, algo=algo_str)
            start = time.perf_counter()
            generate_accounts(cfg)
            elapsed = time.perf_counter() - start
            results.append(
                BenchResult(
                    label=f"{algo_str} ({native_name})",
                    count=count,
                    warmup_sec=0.0,
                    elapsed_sec=elapsed,
                    iterations=1,
                    stddev_sec=0.0,
                )
            )

        # Fallback backend (xrpl-py) — always available
        backend = FallbackBackend(algo)
        start = time.perf_counter()
        for _ in range(count):
            backend.generate_account()
        elapsed = time.perf_counter() - start
        results.append(
            BenchResult(
                label=f"{algo_str} (xrpl-py)",
                count=count,
                warmup_sec=0.0,
                elapsed_sec=elapsed,
                iterations=1,
                stddev_sec=0.0,
            )
        )

    return results


# =============================================================================
# CLI
# =============================================================================


def parse_args(argv: list[str] | None = None):
    """Parse command-line arguments."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Benchmark generate_ledger account, trustline, and pipeline generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--accounts", type=int, default=None, help="Number of accounts to generate")
    parser.add_argument(
        "--target",
        choices=["accounts", "accounts-batch", "accounts-full", "trustlines", "pipeline", "compare"],
        default="accounts",
        help="Benchmark target (default: accounts)",
    )
    parser.add_argument(
        "--algo", choices=["ed25519", "secp256k1"], default="ed25519", help="Algorithm (default: ed25519)"
    )
    parser.add_argument("--gpu", action="store_true", help="Use GPU backend")
    parser.add_argument("--iterations", type=int, default=1, help="Number of iterations (default: 1)")
    parser.add_argument("--json", action="store_true", help="Output JSON to stdout")
    parser.add_argument("--output", type=str, metavar="FILE", help="Write JSON to file")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")
    parser.add_argument("--info", action="store_true", help="Print system info and exit")
    parser.add_argument("--compare", action="store_true", help="Shortcut for --target compare")
    parser.add_argument("--pipeline", action="store_true", help="Shortcut for --target pipeline")

    args = parser.parse_args(argv)

    # Shortcuts
    if args.compare:
        args.target = "compare"
    if args.pipeline:
        args.target = "pipeline"

    return args


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    import json as json_mod

    args = parse_args(argv)

    if args.info:
        info = get_system_info()
        for key, val in info.items():
            print(f"  {key}: {val}", file=sys.stderr)
        return 0

    if args.target == "compare":
        count = args.accounts or 500
        if not args.quiet:
            print(f"Comparing all backends with {count} accounts each...\n", file=sys.stderr)
        results = run_compare(count)
    elif args.accounts is None:
        print("Error: --accounts is required (unless using --compare or --info)", file=sys.stderr)
        return 1
    elif args.target == "accounts":
        results = [run_accounts(args.accounts, algo=args.algo, use_gpu=args.gpu, iterations=args.iterations)]
    elif args.target == "accounts-batch":
        warmup_sec = warmup_gpu()
        result = run_gpu_batch(args.accounts)
        result.warmup_sec = warmup_sec
        results = [result]
    elif args.target == "accounts-full":
        warmup_sec = warmup_gpu()
        result = run_gpu_full(args.accounts)
        result.warmup_sec = warmup_sec
        results = [result]
    elif args.target == "trustlines":
        results = [run_trustlines(count=args.accounts)]
    elif args.target == "pipeline":
        results = [run_pipeline(num_accounts=args.accounts)]
    else:
        print(f"Unknown target: {args.target}", file=sys.stderr)
        return 1

    # Output
    if args.json or args.output:
        data = format_json(results)
        if args.output:
            with open(args.output, "w") as f:
                json_mod.dump(data, f, indent=2)
            print(f"Results written to {args.output}", file=sys.stderr)
        else:
            print(json_mod.dumps(data, indent=2))
    else:
        print(format_table(results))

    return 0


if __name__ == "__main__":
    sys.exit(main())
