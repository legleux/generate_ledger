# TODO

### Split out ledger generation

Consider refactoring the repo to be even less coupled by creating a new repo `ledger_tools` that just includes the 3
components somehow (git submodules?) such that they can stand on their own but be used as one final package.

## P0 — Critical

### Clean up dead code and crufty files from config compositor refactor

- Delete old `.cfg` template files (`xrpld_validator.cfg`, `xrpld_node.cfg`) — no longer used
- Delete `template_idea/` and `template_idea_2/` directories — absorbed into main code
- Audit `xrpld_cfg.py` for unused imports (`string.Template`, etc.) and dead code
- Remove `--peer-port` option definition from `cli/xrpld_cfg.py` if still present (param removed but option may linger)
- Verify no other code references the old template paths (`_VALIDATOR_TEMPLATE`, `_NODE_TEMPLATE`)

### Network startup smoke testing

Every object type should have an associated test that:

1. Generates the network with the objects required in the `ledger.json`
2. Starts the network
3. Confirms transactions using those generated objects succeed (e.g. using a generated account, a `Payment` transaction can be sent)

### Live validation

Verify generated ledgers actually boot on xrpld and amendments are active — not just correct JSON. This is the foundation for smoke testing above.

**Future validations:** Leverage the OpenAPI spec (when available) to aid in object validation testing.

## P1 — High

### Refactor `consolidate_directory_nodes` → protocol-based

Cognitive complexity 33 (threshold 15). Introduce `LedgerObjectGroup` protocol so each object type handles its own state entries, directory entries, and owner counts. New object types just implement the protocol instead of adding branches. Plan: `plans/consolidate_directory_nodes.md`.

### Audit and modularize crypto primitives

`crypto.py`, `crypto_backends.py`, `indices.py`, and `gpu_backend.py` each implement overlapping crypto primitives (SHA-512 Half, RIPEMD-160, base58check, ed25519/secp256k1 key derivation). Audit the full set of primitives we use, compare them against what xrpl-py provides natively, and determine what we actually need to own vs what we can delegate. Goal: a single `crypto/` package with clear boundaries — our custom fast paths (PyNaCl, coincurve, CUDA) vs xrpl-py's implementations, with documented rationale for each divergence.

### Refactor config generation

~~Templatized:~~ ~~validator and non-validator configs now use `string.Template` with separate `.cfg` templates.~~ Replaced with layered TOML compositor: Pydantic models, section generators, `build_config()` file-based composition, `NetworkBuilder` programmatic API. Remaining: keygen should use native backends (PyNaCl) with xrpl-py fallback, same as ledger generation. CLI `gen xrpld compose` subcommand for single-node file-based config.

### Re-introduce UNL usage

Earlier incarnation optionally generated and deployed a bare-bones webserver in the network to serve a UNL that the nodes used. Most of the code exists elsewhere — needs re-introduction and refactoring.

### Split into sub-packages

The package has three core concerns: ledger generation (`ledger.py`, `ledger_builder.py`, `accounts.py`, `trustlines.py`, `amm.py`, `amendments.py`), network topology configs (`xrpld_cfg.py`), and docker compose (`compose.py`). Split into `generate_ledger.ledger`, `generate_ledger.network`, `generate_ledger.compose`.

### Additional ledger objects

Vault/Offers, Escrows, Checks, etc. Vault stub exists in `develop/vault.py` (raises `NotImplementedError`).

### MPT authorization flags

`MPTHolderConfig` doesn't support setting `lsfMPTAuthorized` (0x02) on MPToken objects. If an issuance has `lsfMPTRequireAuth`, pre-generated holders are unauthorized and can't transfer. Add `authorized: bool = True` to `MPTHolderConfig` that sets the flag on the MPToken. Without `lsfMPTRequireAuth` on the issuance (the default), holders work fine.

### Mixed key type accounts

Support generating accounts with mixed key types (ed25519 + secp256k1) in the same ledger.

### Modularize benchmark script for all object types

`scripts/bench_accounts.py` currently benchmarks accounts, trustlines, and the full pipeline. Break it into a proper module structure (e.g. `scripts/bench/`) with a runner per object type so we can easily add benchmarks for AMM pools, MPTs, gateways, directory nodes, and future object types (Vault, Offers) without bloating a single file.

## P2 — Medium

### ~~xrpld config overlay file~~

~~Accept a TOML/JSON overlay file that overrides specific sections of the xrpld.cfg templates.~~ Done — layered TOML compositor (`build_config()`) supports base → env → role → host layers with recursive deep merge.

### Clean up compose.py

Multiple FIXMEs and TODOs: volume mount logic, port exposure for multiple nodes, image entrypoint assumption, ledger file loading for hubs.

### Clean packaging → PyPI deployment

Publish workflow (`.github/workflows/publish.yml`) exists but only targets TestPyPI. Adding real PyPI is straightforward — duplicate the `publish-testpypi` job without the `repository-url` override and add a `pypi` environment.

## P3 — Low

### Update `accounts.json` → inventory file

The project generates more than just accounts now. Create additional files or a single inventory file documenting all generated objects. The `ledger.json` can't solely be used for reference because you need the credentials.

### Branch-per-profile amendment strategy

Use a `release` branch that tracks the latest major xrpld release amendments, and `main`/`develop` for latest develop amendments. Each branch owns its curated amendment list, eliminating runtime GitHub fetching.

### Enforce complexity limits in CI

Add complexipy/radon as CI gate (currently reporting only). Current hotspot: `consolidate_directory_nodes` (33 cognitive). See `plans/complexity.md` for baseline.

### Performance: `--compress` flag

Write `ledger.json.gz` using stdlib `gzip`. 1M accounts: 327 MB → 70 MB.

### Performance: Faster serialization

At 1M accounts, JSON serialization is the bottleneck (~13s of 16s). Options: `orjson` (Rust, ~5-10x faster, drop-in), streaming JSON write, or parallel dict assembly.

### Performance: Binary ledger format

Investigate writing xrpld's native binary ledger format directly instead of JSON. Eliminates serialization overhead entirely.

### Performance: Free-threaded Python (no-GIL)

Python 3.13t+ supports free-threaded mode (no GIL). PyNaCl/coincurve release the GIL during C calls, so `ThreadPoolExecutor` could replace `ProcessPoolExecutor` for CPU account generation — eliminating process spawn overhead (~2s for 50k accounts). Threading gave no speedup under GIL (tested 2026-03-26); re-test with `python3.13t` or `python3.14t` builds.

### Performance: Rigorous benchmark suite

Current timing numbers are ad-hoc one-off measurements. Need a proper benchmark suite that:

- Runs multiple iterations and reports mean/standard deviation
- Tests at key scale points (1k, 10k, 50k, 100k, 250k, 500k, 1M)
- Compares all backends (xrpl-py, PyNaCl, coincurve, GPU) at each scale
- Measures `generate_accounts()` separately from full `gen_ledger_state()` pipeline
- Runs as part of CI or on-demand (not in the test suite — too slow)
- Records results in a machine-readable format for regression tracking

### Performance: Audit CUDA kernel

The CUDA kernel (`src/generate_ledger/cuda/ed25519_accounts.cu`) implements SHA-512, SHA-256, RIPEMD-160, ed25519 scalar multiplication, and base58 encoding. Needs a security/correctness audit:

- Verify ed25519 point arithmetic matches reference implementation (RFC 8032)
- Verify SHA-512/256 and RIPEMD-160 produce correct digests for known test vectors
- Verify base58check encoding matches xrpl-py output for all generated accounts
- Check for GPU-specific issues: race conditions, shared memory correctness, warp divergence
- Profile kernel occupancy and identify optimization opportunities

### Config file for `--trustline` / `--amm-pool` specs

The colon-delimited CLI syntax (`--trustline "0:1:USD:1000000000"`) is fine for a few objects but unwieldy for complex setups. Accept a TOML/JSON/YAML config file defining trustlines, AMM pools, gateways, etc. in a structured format.

## Bugs

### `--accounts N` creates N + default gateways

`--accounts 100` with no `--gateways` flag creates 104 accounts because the default gateway count (4) is added on top. When the user explicitly sets `--accounts`, the default gateways should probably be suppressed (i.e., `--gateways 0` implied) unless `--gateways` is also explicitly provided. The bare `gen` with no arguments should keep the default gateways.

### coincurve fails to build on Debian trixie in CI

Missing `python3-dev` headers in `ghcr.io/astral-sh/uv:python3.X-trixie` containers. coincurve needs CMake + Python development headers to compile from source. CI now fails loudly instead of silently falling back.

### Docker compose startup order

If other validators start before val0, they create their own ledger, leaving val0 disconnected and not using the defined ledger. Workaround: `docker compose up -d val0 && sleep 3 && docker compose up -d`.

### Source code TODOs

- `trustlines.py:41` — Remove `generate_trustset_txn_id` once confirmed xrpld ignores `PreviousTxnID` on genesis objects
- `amm.py:113` — Remove `generate_ammcreate_txn_id` once confirmed (same issue)
- `crypto.py:24` — Remove `sign_and_hash_txn` once confirmed (same issue)
- `compose.py` — ~~Port exposure for multiple nodes~~ addressed by `--expose-all-ports`
- `compose.py:118,148` — Volume mount logic is messy
- `compose.py:121,151` — Ledger file loading for first validator/hub only

## Done

- ~~**Standardize CLI on single framework**~~ — All subcommands use Typer. Bare `gen` runs full pipeline.
- ~~**Remove `--algo` from CLI**~~ — Default to ed25519. Config-file-only option.
- ~~**Fix print() → logging**~~ — Replaced bare `print()` with proper logging/typer.echo.
- ~~**Rename rippled → xrpld**~~ — Files, classes, CLI options, comments, compose binary.
- ~~**Real description in pyproject.toml**~~
- ~~**Test AMM fixes**~~ — 2026-01-28 lsfAMMNode flag fix and account derivation verified.
- ~~**Expose all validator ports**~~ — `--expose-all-ports` CLI option + zero-padded naming.
- ~~**Basic smoke test**~~ — Payment ring test: 100 accounts, async submit, balance verification.
