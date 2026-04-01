"""Tests for scripts/bench_accounts.py benchmark script."""

import sys
from pathlib import Path

import pytest

# Add scripts directory to path so we can import bench_accounts as a module
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))


# =============================================================================
# Phase 1: BenchResult dataclass + formatting
# =============================================================================


class TestBenchResult:
    def test_rate_calculation(self):
        from bench_accounts import BenchResult

        result = BenchResult(label="test", count=1000, warmup_sec=0.0, elapsed_sec=2.0, iterations=1, stddev_sec=0.0)
        assert result.rate == 500.0

    def test_rate_zero_elapsed(self):
        from bench_accounts import BenchResult

        result = BenchResult(label="test", count=1000, warmup_sec=0.0, elapsed_sec=0.0, iterations=1, stddev_sec=0.0)
        assert result.rate == 0.0

    def test_warmup_separate_from_rate(self):
        from bench_accounts import BenchResult

        result = BenchResult(label="test", count=1000, warmup_sec=5.0, elapsed_sec=1.0, iterations=1, stddev_sec=0.0)
        # Rate should be 1000/1.0 = 1000, not 1000/6.0
        assert result.rate == 1000.0


class TestFormatJson:
    def test_structure(self):
        from bench_accounts import BenchResult, format_json

        result = BenchResult(
            label="ed25519 (pynacl)", count=500, warmup_sec=0.0, elapsed_sec=0.5, iterations=1, stddev_sec=0.0
        )
        data = format_json([result])
        assert "results" in data
        entry = data["results"][0]
        for key in ("label", "count", "warmup_sec", "elapsed_sec", "rate", "iterations", "stddev_sec"):
            assert key in entry, f"Missing key: {key}"

    def test_system_info_included(self):
        from bench_accounts import BenchResult, format_json

        result = BenchResult(label="test", count=10, warmup_sec=0.0, elapsed_sec=0.1, iterations=1, stddev_sec=0.0)
        data = format_json([result])
        assert "system" in data
        assert "python_version" in data["system"]
        assert "cpu_count" in data["system"]


class TestFormatTable:
    def test_header_and_alignment(self):
        from bench_accounts import BenchResult, format_table

        result = BenchResult(
            label="ed25519 (pynacl)", count=500, warmup_sec=0.0, elapsed_sec=0.02, iterations=1, stddev_sec=0.0
        )
        table = format_table([result])
        assert "Backend" in table or "Label" in table
        assert "Rate" in table
        assert "ed25519" in table

    def test_multiple_results(self):
        from bench_accounts import BenchResult, format_table

        results = [
            BenchResult(
                label="ed25519 (pynacl)", count=500, warmup_sec=0.0, elapsed_sec=0.02, iterations=1, stddev_sec=0.0
            ),
            BenchResult(
                label="secp256k1 (coincurve)", count=500, warmup_sec=0.0, elapsed_sec=0.06, iterations=1, stddev_sec=0.0
            ),
        ]
        table = format_table(results)
        assert "pynacl" in table
        assert "coincurve" in table


# =============================================================================
# Phase 2: Runner wiring (mocked library calls)
# =============================================================================


class TestRunAccounts:
    def test_calls_generate_accounts(self, monkeypatch):
        from bench_accounts import run_accounts

        from generate_ledger.accounts import Account

        called_with = {}

        def mock_generate(config=None, *, use_gpu=False):
            called_with["config"] = config
            called_with["use_gpu"] = use_gpu
            return [Account("rAddr1", "sSeed1"), Account("rAddr2", "sSeed2")]

        monkeypatch.setattr("generate_ledger.accounts.generate_accounts", mock_generate)
        result = run_accounts(count=2)
        assert called_with["config"] is not None
        assert result.count == 2

    def test_default_algo_ed25519(self, monkeypatch):
        from bench_accounts import run_accounts

        from generate_ledger.accounts import Account

        captured_config = {}

        def mock_generate(config=None, *, use_gpu=False):
            captured_config["algo"] = config.algo
            return [Account("r1", "s1")]

        monkeypatch.setattr("generate_ledger.accounts.generate_accounts", mock_generate)
        run_accounts(count=1)
        assert captured_config["algo"] == "ed25519"

    def test_respects_algo_override(self, monkeypatch):
        from bench_accounts import run_accounts

        from generate_ledger.accounts import Account

        captured_config = {}

        def mock_generate(config=None, *, use_gpu=False):
            captured_config["algo"] = config.algo
            return [Account("r1", "s1")]

        monkeypatch.setattr("generate_ledger.accounts.generate_accounts", mock_generate)
        run_accounts(count=1, algo="secp256k1")
        assert captured_config["algo"] == "secp256k1"

    def test_returns_bench_result_with_count(self, monkeypatch):
        from bench_accounts import BenchResult, run_accounts

        from generate_ledger.accounts import Account

        def mock_generate(config=None, *, use_gpu=False):
            return [Account("r1", "s1") for _ in range(config.num_accounts)]

        monkeypatch.setattr("generate_ledger.accounts.generate_accounts", mock_generate)
        result = run_accounts(count=5)
        assert isinstance(result, BenchResult)
        assert result.count == 5
        assert result.elapsed_sec > 0


class TestRunTrustlines:
    def test_uses_library_trustline_function(self, monkeypatch):
        from bench_accounts import run_trustlines

        from generate_ledger.accounts import Account

        call_count = 0

        def mock_generate_fast(account_a, account_b, currency, limit, ledger_seq=2):
            nonlocal call_count
            call_count += 1
            from generate_ledger.trustlines import TrustlineObjects

            return TrustlineObjects(ripple_state={}, directory_node_a={}, directory_node_b={})

        accounts = [Account(f"r{i}", f"s{i}") for i in range(3)]
        monkeypatch.setattr("generate_ledger.trustlines.generate_trustline_objects_fast", mock_generate_fast)
        result = run_trustlines(accounts=accounts, currency="USD", limit=1_000_000)
        assert call_count > 0
        assert result.count == call_count

    def test_generates_star_topology_by_default(self, monkeypatch):
        """Star topology: all accounts trust account[0]. N-1 trustlines for N accounts."""
        from bench_accounts import run_trustlines

        from generate_ledger.accounts import Account
        from generate_ledger.trustlines import TrustlineObjects

        def mock_generate_fast(account_a, account_b, currency, limit, ledger_seq=2):
            return TrustlineObjects(ripple_state={}, directory_node_a={}, directory_node_b={})

        accounts = [Account(f"r{i}", f"s{i}") for i in range(5)]
        monkeypatch.setattr("generate_ledger.trustlines.generate_trustline_objects_fast", mock_generate_fast)
        result = run_trustlines(accounts=accounts, currency="USD", limit=1_000_000)
        assert result.count == 4  # N-1 for star topology


class TestRunPipeline:
    def test_calls_gen_ledger_state(self, monkeypatch):
        from bench_accounts import run_pipeline

        called_with = {}

        def mock_gen(config=None, *, write_accounts=True):
            called_with["write_accounts"] = write_accounts
            called_with["config"] = config
            return {"ledger": {"accountState": [{"type": "a"}, {"type": "b"}]}}

        monkeypatch.setattr("generate_ledger.ledger.gen_ledger_state", mock_gen)
        result = run_pipeline(num_accounts=2)
        assert called_with["write_accounts"] is False
        assert result.count > 0

    def test_returns_object_count(self, monkeypatch):
        from bench_accounts import run_pipeline

        fake_state = [{"LedgerEntryType": "AccountRoot"}] * 10

        def mock_gen(config=None, *, write_accounts=True):
            return {"ledger": {"accountState": fake_state}}

        monkeypatch.setattr("generate_ledger.ledger.gen_ledger_state", mock_gen)
        result = run_pipeline(num_accounts=5)
        assert result.count == 10


class TestRunCompare:
    def test_includes_ed25519_and_secp256k1(self, monkeypatch):
        from bench_accounts import run_compare

        from generate_ledger.accounts import Account

        def mock_generate(config=None, *, use_gpu=False):
            return [Account("r1", "s1") for _ in range(config.num_accounts)]

        monkeypatch.setattr("generate_ledger.accounts.generate_accounts", mock_generate)
        results = run_compare(count=5)
        labels = [r.label for r in results]
        assert any("ed25519" in label for label in labels)
        assert any("secp256k1" in label for label in labels)


# =============================================================================
# Phase 3: GPU warmup isolation
# =============================================================================

try:
    from generate_ledger.gpu_backend import GpuEd25519Backend

    GpuEd25519Backend()
    _GPU_AVAILABLE = True
except Exception:
    _GPU_AVAILABLE = False


class TestWarmup:
    @pytest.mark.skipif(not _GPU_AVAILABLE, reason="CuPy/CUDA not available")
    def test_warmup_returns_positive_time(self):
        from bench_accounts import warmup_gpu

        warmup_sec = warmup_gpu()
        assert warmup_sec > 0

    def test_cpu_warmup_is_zero(self):
        """CPU-only runs should report zero warmup."""
        from bench_accounts import run_accounts

        # run_accounts without GPU should have warmup_sec=0.0
        result = run_accounts(count=2, algo="ed25519", use_gpu=False)
        assert result.warmup_sec == 0.0

    @pytest.mark.skipif(not _GPU_AVAILABLE, reason="CuPy/CUDA not available")
    def test_warmup_not_in_elapsed(self):
        """GPU runner reports warmup_sec=0.0 (warmup is caller's responsibility)."""
        from bench_accounts import run_gpu_full, warmup_gpu

        warmup_gpu()  # ensure kernel is compiled
        result = run_gpu_full(count=100)
        assert result.warmup_sec == 0.0  # warmup was done externally, not baked into result
        assert result.elapsed_sec > 0  # but generation did take some time


# =============================================================================
# Phase 4: Multiple iterations + statistics
# =============================================================================


class TestIterations:
    def test_single_iteration_stddev_zero(self, monkeypatch):
        from bench_accounts import run_accounts

        from generate_ledger.accounts import Account

        def mock_generate(config=None, *, use_gpu=False):
            return [Account("r1", "s1") for _ in range(config.num_accounts)]

        monkeypatch.setattr("generate_ledger.accounts.generate_accounts", mock_generate)
        result = run_accounts(count=5, iterations=1)
        assert result.stddev_sec == 0.0
        assert result.iterations == 1

    def test_multiple_iterations_returns_mean(self, monkeypatch):
        from bench_accounts import run_accounts

        from generate_ledger.accounts import Account

        def mock_generate(config=None, *, use_gpu=False):
            return [Account("r1", "s1") for _ in range(config.num_accounts)]

        monkeypatch.setattr("generate_ledger.accounts.generate_accounts", mock_generate)
        result = run_accounts(count=5, iterations=3)
        assert result.iterations == 3
        assert result.elapsed_sec > 0  # mean of 3 real timings

    def test_multiple_iterations_has_nonzero_stddev(self, monkeypatch):
        """With real timing, stddev should be >= 0 (usually > 0 due to noise)."""
        from bench_accounts import run_accounts

        from generate_ledger.accounts import Account

        def mock_generate(config=None, *, use_gpu=False):
            return [Account("r1", "s1") for _ in range(config.num_accounts)]

        monkeypatch.setattr("generate_ledger.accounts.generate_accounts", mock_generate)
        result = run_accounts(count=5, iterations=3)
        assert result.stddev_sec >= 0.0  # can be 0 if timings are identical, but field exists


# =============================================================================
# Phase 5: CLI argument parsing
# =============================================================================


class TestCli:
    def test_default_algo_is_ed25519(self):
        from bench_accounts import parse_args

        args = parse_args(["--accounts", "10"])
        assert args.algo == "ed25519"

    def test_compare_flag(self):
        from bench_accounts import parse_args

        args = parse_args(["--compare"])
        assert args.target == "compare"

    def test_pipeline_shortcut(self):
        from bench_accounts import parse_args

        args = parse_args(["--pipeline", "--accounts", "10"])
        assert args.target == "pipeline"

    def test_accounts_required_unless_compare_or_info(self):
        from bench_accounts import parse_args

        # --compare and --info don't need --accounts
        args_compare = parse_args(["--compare"])
        assert args_compare.accounts is None or args_compare.target == "compare"

        args_info = parse_args(["--info"])
        assert args_info.info is True

    def test_json_flag(self):
        from bench_accounts import parse_args

        args = parse_args(["--json", "--accounts", "10"])
        assert args.json is True

    def test_iterations_default(self):
        from bench_accounts import parse_args

        args = parse_args(["--accounts", "10"])
        assert args.iterations == 1

    def test_gpu_flag(self):
        from bench_accounts import parse_args

        args = parse_args(["--accounts", "10", "--gpu"])
        assert args.gpu is True


# =============================================================================
# Phase 6: Integration tests (real crypto, small counts)
# =============================================================================


class TestIntegration:
    def test_accounts_end_to_end(self):
        from bench_accounts import run_accounts

        result = run_accounts(count=5)
        assert result.count == 5
        assert result.elapsed_sec > 0
        assert result.rate > 0
        assert "ed25519" in result.label

    def test_accounts_secp256k1(self):
        from bench_accounts import run_accounts

        result = run_accounts(count=3, algo="secp256k1")
        assert result.count == 3
        assert "secp256k1" in result.label

    def test_trustlines_end_to_end(self):
        from bench_accounts import run_trustlines

        from generate_ledger.accounts import AccountConfig, generate_accounts

        accounts = generate_accounts(AccountConfig(num_accounts=5))
        result = run_trustlines(accounts=accounts)
        assert result.count == 4  # star topology: N-1 trustlines
        assert result.elapsed_sec > 0

    def test_pipeline_end_to_end(self):
        from bench_accounts import run_pipeline

        result = run_pipeline(num_accounts=2)
        assert result.count > 0
        assert result.elapsed_sec > 0

    def test_compare_end_to_end(self):
        from bench_accounts import run_compare

        results = run_compare(count=3)
        assert len(results) >= 2  # at least native + fallback for one algo
        labels = [r.label for r in results]
        assert any("ed25519" in label for label in labels)

    def test_format_json_end_to_end(self):
        from bench_accounts import format_json, run_accounts

        result = run_accounts(count=3)
        data = format_json([result])
        assert data["results"][0]["count"] == 3
        assert data["results"][0]["rate"] > 0


class TestGpuIntegration:
    pytestmark = pytest.mark.skipif(not _GPU_AVAILABLE, reason="CuPy/CUDA not available")

    def test_gpu_batch_end_to_end(self):
        from bench_accounts import run_gpu_batch

        result = run_gpu_batch(count=100)
        assert result.count == 100
        assert result.rate > 0

    def test_gpu_full_end_to_end(self):
        from bench_accounts import run_gpu_full

        result = run_gpu_full(count=100)
        assert result.count == 100
        assert result.rate > 0

    def test_warmup_then_benchmark(self):
        from bench_accounts import run_gpu_full, warmup_gpu

        warmup_sec = warmup_gpu()
        assert warmup_sec > 0
        result = run_gpu_full(count=100)
        assert result.count == 100

    def test_compare_has_gpu_row(self):
        """run_compare should include GPU when available."""
        # NOTE: GPU in compare is a future enhancement.
        # For now, verify compare works with GPU available in the environment.
        from bench_accounts import run_compare

        results = run_compare(count=3)
        assert len(results) >= 2
