# Plan: Separate Ledger / Config / Compose Module Boundaries

## Context

The three core domains — **ledger** (`ledger.py`), **config** (`xrpld_cfg.py`), and **compose** (`compose.py`) — are already cleanly separated at the library level (zero cross-imports). The coupling lives entirely in the CLI orchestration layer:

- `config.py` is a confusing barrel that re-exports both `ComposeConfig` and `LedgerConfig`
- `run_full_pipeline()` takes 13 flat params mixing all three domains, then constructs `XrpldConfigSpec` and `ComposeConfig` inline
- `cli/main.py::root()` passes shared params (fees, amendments) to both ledger and xrpld without clear boundaries

**Goal:** Make the pipeline a pure sequencer that receives pre-built config objects. Each domain constructs its own config independently. Shared CLI values (fees, amendments) are passed explicitly at the call site.

## Changes

### 1. Delete `config.py` barrel module

- **Delete** `src/generate_ledger/config.py` (8 lines — just re-exports)
- **Delete** `tests/lib/test_config_reexport.py` (the only test for this barrel)
- **Update** `shared_options.py:138` — change `from generate_ledger.config import ComposeConfig` → `from generate_ledger.compose import ComposeConfig`

### 2. Add `build_xrpld_config()` and `build_compose_config()` helpers to `shared_options.py`

Mirror the existing `build_ledger_config()` pattern:

- `build_xrpld_config(num_validators, base_dir, peer_port, amendment_profile, amendment_source, amendment_majority_time, reference_fee, account_reserve, owner_reserve, log_level)` → `XrpldConfigSpec`
  - Moves amendment resolution (`get_amendments_for_profile` → feature names) out of `run_full_pipeline` and into this builder
- `build_compose_config(num_validators, base_dir, image, expose_all_ports)` → `ComposeConfig`
  - Moves image tag splitting out of `run_full_pipeline` and into this builder

### 3. Refactor `run_full_pipeline()` signature

Replace 13 flat params with 3 structured objects:

```python
def run_full_pipeline(
    *,
    output_dir: Path,
    ledger_config,       # LedgerConfig
    xrpld_config_spec,   # XrpldConfigSpec
    compose_config,      # ComposeConfig
)
```

The function becomes a pure sequencer: write ledger → write xrpld configs → write compose. No domain logic inside.

### 4. Update `cli/main.py::root()` call site

Construct all three config objects before calling `run_full_pipeline()`:

```python
ledger_config = build_ledger_config(...)      # already exists
xrpld_spec = build_xrpld_config(...)          # new
compose_cfg = build_compose_config(...)        # new
run_full_pipeline(output_dir=..., ledger_config=..., xrpld_config_spec=..., compose_config=...)
```

Shared params (`base_fee`, `reserve_base`, `reserve_inc`, `amendment_profile`, `amendment_source`) are passed explicitly to each builder from the CLI values. This is the right place for the mapping — visible, one location, no hidden coupling.

## Files to modify

- `src/generate_ledger/config.py` — **delete**
- `tests/lib/test_config_reexport.py` — **delete**
- `src/generate_ledger/cli/shared_options.py` — add 2 builder functions, refactor `run_full_pipeline()`
- `src/generate_ledger/cli/main.py` — update `root()` to use new builders and simplified pipeline call

## What does NOT change

- CLI interface (flags, defaults, behavior) — identical
- Library modules (`ledger.py`, `compose.py`, `xrpld_cfg.py`) — untouched
- `cli/ledger.py` and `cli/xrpld_cfg.py` subcommands — they build configs directly, don't use `run_full_pipeline`
- `build_ledger_config()` — already clean

## Verification

```bash
pytest                    # all ~437 tests pass
ruff check .              # no lint issues
uv run gen --help         # CLI unchanged
uv run gen ledger --help  # subcommand unchanged
uv run gen xrpld --help   # subcommand unchanged
```
