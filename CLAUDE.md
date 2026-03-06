# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

`generate_ledger` generates custom XRPL genesis ledgers and complete test network environments — accounts, trustlines, AMM pools, validator configs, and docker-compose — in seconds. It produces `ledger.json` files that bootstrap rippled nodes with pre-funded accounts and enabled amendments.

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
gen ledger --accounts 10 --output-dir ./out
gen auto --accounts 50 --validators 5 --output-dir ./testnet
```

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
- **`ledger_types.py`** — Config types extracted from `ledger.py`: `ExplicitTrustline`, `FeeConfig`, `MPTIssuanceConfig`, `MPTHolderConfig`, `AMMPoolConfig` (re-exported from `gl.ledger` for backward compat)

### Core Pipeline

The main data flow is in `ledger.py:gen_ledger_state()`:

1. **`accounts.py`** — Generates XRPL accounts (keypairs, addresses) using xrpl-py or native crypto backends (PyNaCl for ed25519). Also provides `resolve_account_ref()` and `resolve_account_to_object()` for account reference resolution
2. **`trustlines.py`** — Generates RippleState + DirectoryNode objects for trustlines. Provides shared builders: `order_low_high()`, `build_ripple_state()`, `build_directory_node()`, `generate_trustline_objects_fast()` (used by gateways and AMM)
3. **`gateways.py`** — Generates gateway topology trustlines (star/mesh from issuer accounts). Imports `generate_trustline_objects_fast` from `trustlines.py`
4. **`amm.py`** — Generates AMM pool objects (AMM entry, pseudo-account, LP tokens, asset trustlines). Uses shared builders from `trustlines.py` and constants from `constants.py`
5. **`amendments.py`** — Loads amendment hashes (profile-based with auto-fetch: release queries mainnet RPC, develop fetches features.macro from GitHub, custom loads user JSON)
6. **`develop/`** — Optional package for pre-release objects (MPT, Vault stubs); absent on `main` branch
7. **`ledger_builder.py:assemble_ledger_json()`** — Assembles all objects into final `ledger.json` structure with DirectoryNode consolidation, OwnerCount tracking, and genesis account balance calculation

### XRPL Crypto Primitives

`crypto.py` provides `sha512_half()` and `ripesha()`. `indices.py` builds on these to compute ledger object indices (AccountRoot, RippleState, AMM, etc.) using XRPL's hash prefix scheme (e.g., `0x0061` for AccountRoot, `0x0041` for AMM).

### CLI Structure

Entry point: `gen` (defined in `pyproject.toml` → `generate_ledger.cli.main:cli`). Subcommands: `ledger`, `validators`, `compose`, `auto`. CLI option parsing for colon-delimited formats (trustlines, AMM pools) lives in `cli/parsers.py`.

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
- **Coverage**: enforced at 85% minimum (`fail_under = 85`), currently ~89%
- **Default addopts**: `-rP --cov --cov-report=term-missing:skip-covered`
- **CI matrix**: Python 3.12, 3.13, 3.14 on Debian bookworm + trixie

### Key Test Fixtures (conftest.py)

- `_sandbox_base_dir` (autouse) — Redirects `GL_BASE_DIR` to tmp_path so tests never touch real files
- `_no_network_amendment_fetch` (autouse) — Blocks GitHub fetch and mainnet RPC; develop profile falls back to `GL_FEATURES_MACRO` env var pointing at `tests/data/features_develop.macro`, release profile falls back to bundled `amendments_mainnet.json`
- `alice_account` / `bob_account` — Deterministic accounts with known addresses/seeds
- `sample_amendment_hashes` — Loads from test fixture `tests/data/amendments_develop.json`
- `MAINNET_AMENDMENT_COUNT`, `MAINNET_RETIRED_COUNT`, etc. — Derived from `amendments_mainnet.json` at import time so tests stay in sync with data
- Known-good index constants: `GENESIS_INDEX`, `ALICE_INDEX`, `BOB_INDEX`, `AMENDMENTS_INDEX` (verified against running rippled)

### Test Organization

- `tests/lib/` — Unit tests for core modules (indices, accounts, trustlines, amm, amendments, etc.)
- `tests/cli/` — CLI smoke tests and parser tests
- `tests/integration/` — Full pipeline tests through `gen_ledger_state()`

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
- MPT (Multi-Purpose Tokens) — implemented in `develop/mpt.py` (develop branch only)
- Fast ed25519 account generation via PyNaCl (~22k/sec), GPU backend via CuPy (~580k/sec)
- Test suite: ~434 tests across unit, CLI, and integration (GPU tests auto-skip without CUDA)

### Planned (v2.0)
- Vault/Lending — stub in `develop/vault.py`, raises `NotImplementedError`
- Pre-created Offers in genesis ledger
- Package rename to "ledgen"

### Key Spec Files
- `specs/001-xrpl-ledger-generator/spec.md`
- `specs/001-xrpl-ledger-generator/tasks.md`
- `specs/001-xrpl-ledger-generator/plan.md`

## TODOs

See the detailed TODO list and milestones in the [spec files](specs/001-xrpl-ledger-generator/). Priority items:

1. **Live validation** — Verify generated ledgers boot on rippled and amendments are actually active (not just correct JSON)
2. **Test AMM fixes** — Verify 2026-01-28 lsfAMMNode flag fix and account derivation fix work end-to-end
3. **Vault/Lending** — Implement `develop/vault.py` (currently raises `NotImplementedError`)
4. **Clean packaging** — Real description in pyproject.toml, automatic PyPI deployment
5. **Branch-per-profile amendment strategy** — Use a `release` branch that tracks the latest major rippled release amendments, and `main`/`develop` for latest develop amendments. Each branch owns its curated amendment list, eliminating the need for runtime GitHub fetching and keeping profiles in sync with their corresponding rippled branches.
6. **Enforce complexity limits** — Add complexipy/radon to CI or pre-commit. Current hotspots: `assemble_ledger_json` (68 cognitive), `parse_mpt_spec` (27), `parse_amm_pool` (29), `ledger` CLI (21), `gen_ledger_state` (19). Target: break these down to under 15.
