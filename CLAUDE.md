# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

`generate_ledger` generates custom XRPL genesis ledgers and complete test network environments — accounts, trustlines, AMM pools, validator configs, and docker-compose — in seconds. It produces `ledger.json` files that bootstrap xrpld nodes with pre-funded accounts and enabled amendments.

## Commands

```bash
# Install dependencies
uv sync

# Run all tests (includes coverage report, fails under 85%)
pytest

# Run a single test file
pytest tests/lib/test_amm.py

# Run a single test by name
pytest tests/lib/test_amm.py -k "test_amm_index_calculation"

# Lint
ruff check .

# Fix lint issues
ruff check . --fix

# CLI entry point (after uv sync)
uv run gen                                      # full testnet
uv run gen ledger --accounts 10 --output-dir ./out  # just a ledger
uv run gen xrpld --validators 5                 # just xrpld configs

# Serve docs locally
uv run mkdocs serve

# Smoke test (requires Docker)
pytest tests/smoke/ -m smoke --no-cov -v -s
SMOKE_KEEP_NETWORK=1 pytest tests/smoke/ -m smoke --no-cov -v -s  # keep network running
```

### Documentation

Built with mkdocs-material. Source in `docs/`, config in `mkdocs.yml`, build output in `site/` (gitignored).

- `uv run mkdocs serve` — live preview at http://127.0.0.1:8000
- `uv run mkdocs build` — static site to `site/`
- Pages: index, quickstart, how it works, CLI reference, library API, amendments, development

## Architecture

### Package Alias: `gl` → `generate_ledger`

The package is installed as `generate_ledger` (under `src/generate_ledger/`), with a thin alias package at `src/gl/__init__.py` that re-exports everything. **All official code (src, tests, docs) uses the full `generate_ledger.*` import path.** The `gl` alias exists only as a developer convenience and should not be used in committed code.

```python
from generate_ledger.accounts import Account, generate_accounts
from generate_ledger.indices import account_root_index
from generate_ledger.amendments import get_enabled_amendment_hashes
```

### Shared Modules

- **`constants.py`** — Centralized XRPL flag constants (`LSF_DEFAULT_RIPPLE`, `AMM_ACCOUNT_FLAGS`, `TXN_PREFIX`, `NEUTRAL_ISSUER`) used across trustlines, AMM, and ledger_builder
- **`ledger_types.py`** — Config types extracted from `ledger.py`: `ExplicitTrustline`, `FeeConfig`, `MPTIssuanceConfig`, `MPTHolderConfig`, `AMMPoolConfig` (re-exported from `generate_ledger.ledger` for backward compat)

### Core Pipeline

The main data flow is in `ledger.py:gen_ledger_state()`:

1. **`accounts.py`** — Generates XRPL accounts (keypairs, addresses) using xrpl-py or native crypto backends (PyNaCl for ed25519). Also provides `resolve_account_ref()` and `resolve_account_to_object()` for account reference resolution
2. **`trustlines.py`** — Generates RippleState + DirectoryNode objects for trustlines. Provides shared builders: `order_low_high()`, `build_ripple_state()`, `build_directory_node()`, `generate_trustline_objects_fast()` (used by gateways and AMM)
3. **`gateways.py`** — Generates gateway topology trustlines (star/mesh from issuer accounts). Imports `generate_trustline_objects_fast` from `trustlines.py`
4. **`amm.py`** — Generates AMM pool objects (AMM entry, pseudo-account, LP tokens, asset trustlines). Uses shared builders from `trustlines.py` and constants from `constants.py`
5. **`mpt.py`** — Generates MPTokenIssuance + MPToken objects (MPTokensV1 amendment, enabled on mainnet since 2025-10-01)
6. **`amendments.py`** — Loads amendment hashes (profile-based with auto-fetch: release queries mainnet RPC, develop fetches features.macro from GitHub, custom loads user JSON)
7. **`develop/`** — Optional package for pre-release objects (Vault stub); absent on `main` branch
8. **`xrpld_cfg.py`** — Layered TOML config compositor for xrpld.cfg generation. Pydantic models (`XrpldNodeConfig` + sub-models) with role-based validation. Individual `gen_*` section generators registered in `SECTION_GENERATORS` produce `Section(name, lines)` objects; `build_sections()` collects them, `render_sections()` serializes to INI format. Two entry points: `XrpldConfigSpec` (programmatic, generates N validators + 1 node for CLI, reads defaults from TOML layers) and `build_config()` (file-based, loads TOML layers from `config/` — base → env → role → host). Bundled TOML layers in `src/generate_ledger/config/`
9. **`ledger_builder.py:assemble_ledger_json()`** — Assembles all objects into final `ledger.json` structure; delegates DirectoryNode consolidation and OwnerCount tracking to `directory_nodes.py`
10. **`directory_nodes.py`** — DirectoryNode consolidation: merges per-object directory entries into per-account directories with sorted Indexes

### XRPL Crypto Primitives

`crypto.py` provides `sha512_half()`, `ripesha()`, and `sign_and_hash_txn()` (shared transaction signing). `indices.py` builds on these to compute ledger object indices (AccountRoot, RippleState, AMM, etc.) using XRPL's hash prefix scheme (e.g., `0x0061` for AccountRoot, `0x0041` for AMM).

### CLI Structure

Entry point: `gen` (Typer app in `cli/main.py`, exported as Click-compatible via `get_command()` in `pyproject.toml` → `generate_ledger.cli.main:cli`). Invoking `gen` with no subcommand runs the full 3-step pipeline (ledger + xrpld configs + docker-compose). Subcommands `ledger` and `xrpld` run individual steps.

Key CLI modules:

- **`cli/main.py`** — Typer root app with full pipeline as default action; mounts sub-apps via `add_typer()`
- **`cli/ledger.py`** — `gen ledger` command (Typer app) — ledger.json generation only
- **`cli/xrpld_cfg.py`** — `gen xrpld` command (Typer app) — xrpld.cfg generation only (supports `--log-level`)
- **`cli/shared_options.py`** — Shared config-building and pipeline logic (used by root and `gen ledger`)
- **`cli/parsers.py`** — CLI option parsing for colon-delimited formats (trustlines, AMM pools, MPT specs)

### Configuration

`LedgerConfig` (in `ledger.py`) is a pydantic-settings `BaseSettings` class. Supports env vars with `GL_` prefix, `.env` files, and nested config via `GL_ACCOUNT__NUM_ACCOUNTS` etc.

### Library API

The package can be used programmatically (not just via CLI). Key entry points:

- `gen_ledger_state(config, *, write_accounts=False) -> dict` — pure in-memory ledger generation
- `write_ledger_file(output_file, config, *, quiet=True) -> Path` — write to disk without console output

See `docs/library-usage.md` for full usage guide.

### Branch Strategy

- `main` = release (no `develop/` package)
- `develop` = includes `develop/` with experimental object builders (MPT, Vault)
- The `develop/` package uses graceful `ImportError` handling so `main` branch code never breaks

## Code Style

- **Line length**: 120 (configured in `pyproject.toml`)
- **Linter**: ruff with rules `E, F, I, W, B, UP, ISC, PL, RUF`
- **Target**: Python 3.13 (`target-version = "py313"`)
- **Excluded from lint**: none (legacy exclusions removed)
- **Test-specific ignores**: `PLR2004` (magic values) and `PLC0415` (imports not at top) are allowed in tests

## Testing

- **Framework**: pytest with pytest-cov
- **Coverage**: enforced at 85% minimum (`fail_under = 85`), currently ~92%
- **Default addopts**: `-rP --cov --cov-report=term-missing:skip-covered`
- **CI matrix**: Python 3.12, 3.13, 3.14 on Debian bookworm + trixie, plus macOS latest

### Key Test Fixtures (conftest.py)

- `_sandbox_base_dir` (autouse) — Redirects `GL_BASE_DIR` to tmp_path so tests never touch real files
- `_no_network_amendment_fetch` (autouse) — Blocks GitHub fetch and mainnet RPC; develop profile falls back to `GL_FEATURES_MACRO` env var pointing at `tests/data/features_develop.macro`, release profile falls back to bundled `amendments_mainnet.json`
- `alice_account` / `bob_account` — Deterministic accounts with known addresses/seeds
- `sample_amendment_hashes` — Loads from test fixture `tests/data/amendments_develop.json`
- `MAINNET_AMENDMENT_COUNT`, `MAINNET_RETIRED_COUNT`, etc. — Derived from `amendments_mainnet.json` at import time so tests stay in sync with data
- Known-good index constants: `GENESIS_INDEX`, `ALICE_INDEX`, `BOB_INDEX`, `AMENDMENTS_INDEX` (verified against running xrpld)

### Test Organization

- `tests/lib/` — Unit tests for core modules (indices, accounts, trustlines, amm, amendments, etc.)
- `tests/cli/` — CLI tests and parser tests
- `tests/integration/` — Full pipeline tests through `gen_ledger_state()`
- `tests/smoke/` — Network smoke tests (Docker required, skipped by default, run with `-m smoke`). Payment ring uses full consensus network; AMM and MPT tests use standalone mode (single container, `ledger_accept` RPC)

## Working Principles

**CLAUDE.md Maintenance**: This file MUST be updated when:

- New modules are added to the project structure
- Significant architectural changes are made
- Commands or workflows change

## Project Status

### Complete

- Accounts + Trustlines generation (US1)
- Validator configs + UNL (US2)
- Docker compose generation (US3)
- AMM pools with LP tokens, asset trustlines, DirectoryNode consolidation (US5)
- Amendment system: profiles (release/develop/custom), features.macro parser, per-amendment overrides, auto-fetch from GitHub (develop) and mainnet RPC (release) with offline fallbacks
- Gateway topology (star/mesh), fast trustline generation, lsfDefaultRipple on issuers
- MPT (Multi-Purpose Tokens) — `mpt.py` (promoted from develop/, MPTokensV1 enabled on mainnet since 2025-10-01)
- Fast ed25519 account generation via PyNaCl (~25k/sec), GPU backend via CuPy (~535k/sec with indices)
- Test suite: ~548 unit/CLI/integration tests (GPU tests skip without CUDA) + 3 smoke tests (Docker, skipped by default)
- Smoke tests: Payment ring (100 accounts, async submit, balance verification), AMM CLOB (issued/issued pools cross OfferCreate), MPT transfer (issuance → authorize → fund → transfer)

### Planned (v2.0)

- Vault/Lending — stub in `develop/vault.py`, raises `NotImplementedError`
- Pre-created Offers in genesis ledger
- Package rename to "ledgen"

## TODOs

See [TODO.md](TODO.md) for the prioritized, consolidated task list.
