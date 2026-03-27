# Development

## Setup

Clone the repository and install dependencies:

```bash
git clone https://github.com/legleux/generate_ledger.git
cd generate_ledger
uv sync
```

For fast crypto backends (recommended for development):

```bash
uv sync --group fast   # + PyNaCl, coincurve
```

To also install GPU backends (requires NVIDIA GPU):

```bash
uv sync --group gpu    # CuPy + CUDA toolkit wheels
```

## Running Tests

The test suite uses pytest with a coverage threshold of 85% (currently ~89%).

```bash
# Run all tests
uv pytest

# Run a single test file
uv pytest tests/lib/test_amm.py

# Run a single test by name
uv pytest tests/lib/test_amm.py -k "test_amm_index_calculation"
```

Default pytest options (configured in `pyproject.toml`):

```
addopts = "-rP --cov --cov-report=term-missing:skip-covered"
```

### Test Organization

| Directory            | Contents                                                                           |
| -------------------- | ---------------------------------------------------------------------------------- |
| `tests/lib/`         | Unit tests for core modules (indices, accounts, trustlines, AMM, amendments, etc.) |
| `tests/cli/`         | CLI smoke tests and parser tests                                                   |
| `tests/integration/` | Full pipeline tests through `gen_ledger_state()`                                   |

### Key Test Fixtures

Defined in `tests/conftest.py`:

- **`_sandbox_base_dir`** (autouse) -- Redirects `GL_BASE_DIR` to a temp directory so tests never touch real files
- **`alice_account` / `bob_account`** -- Deterministic accounts with known addresses and seeds
- **`sample_amendment_hashes`** -- Loads from test fixture data

## GPU Backend

The `gpu` dependency group installs CuPy and the CUDA toolkit as pre-built pip wheels — no system CUDA install needed. Just an NVIDIA GPU with drivers.

```bash
uv sync --group gpu
uv run pytest  # GPU tests run automatically
```

`CUDA_PATH` is auto-detected from the installed `nvidia-cuda-nvcc` wheel. GPU tests skip gracefully when the GPU group isn't installed or no GPU is available.

## Linting

The project uses [ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
# Check for issues
ruff check .

# Auto-fix issues
ruff check . --fix
```

Configuration (from `pyproject.toml`):

- Line length: 120
- Target: Python 3.13
- Rules: `E, F, I, W, B, UP, ISC, PL, RUF`

## Local CI with test-matrix.sh

The `scripts/test-matrix.sh` script runs Docker containers that match the GitHub Actions CI matrix, so you can validate across Python versions locally:

```bash
scripts/test-matrix.sh
```

The CI matrix tests against Python 3.12, 3.13, and 3.14 on Debian bookworm and trixie.

## Complexity Tools

The dev dependency group includes tools for measuring code complexity:

- **complexipy** -- Cognitive complexity analysis
- **radon** -- Cyclomatic complexity and maintainability index

```bash
uv run complexipy src/generate_ledger/
uv run radon cc src/generate_ledger/ -a
```

## Building

```bash
uv build
```

This produces both sdist and wheel distributions in the `dist/` directory.

## Benchmarks

Benchmark scripts live in `scripts/`:

```bash
# Account generation benchmark
uv run scripts/bench_accounts.py --accounts 10000 --algo ed25519 --mode seq
```

See `scripts/README.md` for detailed benchmark documentation.

## Branch Strategy

| Branch    | Contents                                                                       |
| --------- | ------------------------------------------------------------------------------ |
| `main`    | Release-ready code. No `develop/` package.                                     |
| `develop` | Includes `develop/` subpackage with experimental object builders (MPT, Vault). |

The `develop/` package uses graceful `ImportError` handling so `main` branch code never breaks when `develop/` is absent.
