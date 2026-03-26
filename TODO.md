# TODO

## P0 — Critical

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

### Refactor config generation

Minor validator/non-validator code duplication but the main issue is that the topology is not configurable enough. Use native keygen backends (PyNaCl) with xrpl-py fallback, same as ledger generation.

### Re-introduce UNL usage

Earlier incarnation optionally generated and deployed a bare-bones webserver in the network to serve a UNL that the nodes used. Most of the code exists elsewhere — needs re-introduction and refactoring.

### Split into sub-packages

The package has three core concerns: ledger generation (`ledger.py`, `ledger_builder.py`, `accounts.py`, `trustlines.py`, `amm.py`, `amendments.py`), network topology configs (`xrpld_cfg.py`), and docker compose (`compose.py`). Split into `generate_ledger.ledger`, `generate_ledger.network`, `generate_ledger.compose`.

### Additional ledger objects

Vault/Offers, Escrows, Checks, etc. Vault stub exists in `develop/vault.py` (raises `NotImplementedError`).

### Mixed key type accounts

Support generating accounts with mixed key types (ed25519 + secp256k1) in the same ledger.

## P2 — Medium

### xrpld config overlay file

Accept a TOML/JSON overlay file that overrides specific sections of the xrpld.cfg template (node_size, ports, database paths, etc.) without maintaining a full custom template. Currently `--template-path` is the only way to customize beyond the parameterized options (`--log-level`, `--peer-port`, fees, amendments).

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

### Config file for `--trustline` / `--amm-pool` specs

The colon-delimited CLI syntax (`--trustline "0:1:USD:1000000000"`) is fine for a few objects but unwieldy for complex setups. Accept a TOML/JSON/YAML config file defining trustlines, AMM pools, gateways, etc. in a structured format.

## Bugs

### Docker compose startup order

If other validators start before val0, they create their own ledger, leaving val0 disconnected and not using the defined ledger. Workaround: `docker compose up -d val0 && sleep 3 && docker compose up -d`.

### Source code TODOs

- `trustlines.py:41` — Remove `generate_trustset_txn_id` once confirmed xrpld ignores `PreviousTxnID` on genesis objects
- `amm.py:113` — Remove `generate_ammcreate_txn_id` once confirmed (same issue)
- `crypto.py:24` — Remove `sign_and_hash_txn` once confirmed (same issue)
- `compose.py:92` — Port exposure for multiple nodes unclear
- `compose.py:95` — Port mapping logic needs rework
- `compose.py:118,148` — Volume mount logic is messy
- `compose.py:121,151` — Ledger file loading for first validator/hub only

## Done

- ~~**Standardize CLI on single framework**~~ — All subcommands use Typer. Bare `gen` runs full pipeline.
- ~~**Remove `--algo` from CLI**~~ — Default to ed25519. Config-file-only option.
- ~~**Fix print() → logging**~~ — Replaced bare `print()` with proper logging/typer.echo.
- ~~**Rename rippled → xrpld**~~ — Files, classes, CLI options, comments, compose binary.
- ~~**Real description in pyproject.toml**~~
- ~~**Test AMM fixes**~~ — 2026-01-28 lsfAMMNode flag fix and account derivation verified.
