# Project Guide

This page is a broad map of `generate_ledger`: what it builds, how the pieces fit
together, and where to look when changing the code.

## Purpose

`generate_ledger` is a toolkit for building XRPL genesis ledger state and local
test network scaffolding. It is mainly useful when you need a private network that
starts with useful state already present instead of creating everything by
submitting transactions after boot.

The project supports three overlapping workflows:

| Workflow          | Command             | Output                                                                  |
| ----------------- | ------------------- | ----------------------------------------------------------------------- |
| Full test network | `uv run gen`        | `ledger.json`, `accounts.json`, `xrpld.cfg` files, `docker-compose.yml` |
| Ledger only       | `uv run gen ledger` | `ledger.json` and `accounts.json`                                       |
| xrpld config only | `uv run gen xrpld`  | Per-node `xrpld.cfg` files                                              |

## Generated State

The ledger generator can create:

- Funded `AccountRoot` entries
- Explicit or random `RippleState` trustlines
- Gateway-issued asset topology
- AMM ledger objects and AMM pseudo-accounts
- MPT issuance and holder objects
- Sponsorship objects for sponsored fee and reserve relationships
- `DirectoryNode` ownership indexes
- `FeeSettings`
- `Amendments`

The full network generator adds:

- Validator and non-validator `xrpld.cfg` files
- Validator key material
- UNL and peer discovery configuration
- Docker Compose services for the generated nodes

## Data Flow

At a high level, the root CLI command runs this pipeline:

1. Parse CLI options into a `LedgerConfig`.
2. Generate accounts and write `accounts.json`.
3. Generate requested ledger objects: trustlines, gateways, AMMs, MPTs, sponsorships, fees, and amendments.
4. Consolidate owner directories and owner counts.
5. Write `ledger.json`.
6. Generate `xrpld.cfg` files for validators and the hub node.
7. Write `docker-compose.yml`.

For library users, `generate_ledger.ledger.gen_ledger_state()` runs the ledger
portion in memory and returns the JSON-compatible dictionary.

## Code Map

| Module                            | Responsibility                                                        |
| --------------------------------- | --------------------------------------------------------------------- |
| `generate_ledger.cli.main`        | Root `gen` command and full pipeline orchestration                    |
| `generate_ledger.cli.ledger`      | `gen ledger` command                                                  |
| `generate_ledger.cli.xrpld_cfg`   | `gen xrpld` command                                                   |
| `generate_ledger.cli.parsers`     | CLI string spec parsing for trustlines, AMMs, MPTs, and sponsorships  |
| `generate_ledger.ledger`          | `LedgerConfig`, ledger pipeline, and public ledger API                |
| `generate_ledger.ledger_builder`  | Final XRPL ledger JSON assembly                                       |
| `generate_ledger.accounts`        | Account generation, account JSON, and index-friendly account metadata |
| `generate_ledger.crypto_backends` | Native and fallback account-generation backends                       |
| `generate_ledger.gpu_backend`     | Optional CuPy/CUDA ed25519 backend                                    |
| `generate_ledger.indices`         | Deterministic XRPL object index formulas                              |
| `generate_ledger.trustlines`      | Trustline and owner directory object generation                       |
| `generate_ledger.gateways`        | Issuer account and issued-asset trustline topology                    |
| `generate_ledger.amm`             | AMM pool, LP token, and AMM pseudo-account objects                    |
| `generate_ledger.mpt`             | Multi-Purpose Token object generation                                 |
| `generate_ledger.sponsor`         | Sponsor amendment Sponsorship object generation                       |
| `generate_ledger.amendments`      | Amendment source loading, profiles, overrides, and hashes             |
| `generate_ledger.directory_nodes` | Directory node merge and validation helpers                           |
| `generate_ledger.xrpld_cfg`       | Layered config loading and `xrpld.cfg` rendering                      |
| `generate_ledger.compose`         | Docker Compose model and writer                                       |

## Configuration Model

Most runtime options are represented as pydantic settings models. The important
ones are:

- `AccountConfig`: account count, algorithm, balance, GPU usage
- `TrustlineConfig`: random trustline count, currencies, limits
- `GatewayConfig`: gateway count, assets, coverage, connectivity, RNG seed
- `AMMPoolConfig`: AMM asset pair, deposits, fee, creator
- `MPTIssuanceConfig`: issuer, sequence, optional limits and metadata
- `SponsorshipConfig`: owner, sponsee, fee bucket, max fee, reserve count, flags
- `FeeConfig`: base fee and reserve values
- `LedgerConfig`: top-level ledger configuration
- `ComposeConfig`: Docker Compose generation settings
- `XrpldConfigSpec`: node config generation settings

`LedgerConfig` reads `GL_`-prefixed environment variables and supports nested
settings with `__`, for example:

```bash
export GL_BASE_DIR=/tmp/testnet
export GL_ACCOUNT_CFG__NUM_ACCOUNTS=100
```

## Amendment Profiles

Amendments are important because some object types only make sense when the
network starts with the right protocol features enabled.

| Profile   | Use case                                                                     |
| --------- | ---------------------------------------------------------------------------- |
| `release` | Match currently enabled mainnet-style amendments, with bundled fallback data |
| `develop` | Enable supported amendments from an `xrpld` `features.macro` source          |
| `custom`  | Load amendments from a user-provided JSON file                               |

CLI overrides can force individual amendments on or off:

```bash
uv run gen ledger --enable-amendment SomeFeature --disable-amendment Clawback
```

## Testing

The test suite is grouped by intent:

| Path                 | Focus                                                                |
| -------------------- | -------------------------------------------------------------------- |
| `tests/lib/`         | Core object builders, config, indices, merging, amendments, backends |
| `tests/cli/`         | CLI behavior and parser coverage                                     |
| `tests/integration/` | End-to-end ledger generation paths                                   |
| `tests/smoke/`       | Docker-backed network smoke tests                                    |
| `tests/scripts/`     | Release and benchmark helper scripts                                 |

Common commands:

```bash
uv run pytest
uv run pytest tests/lib/test_amm.py
uv run pytest -m smoke
uv run ruff check .
```

By default, smoke tests are excluded by the pytest marker expression in
`pyproject.toml`.

## Documentation And Scripts

The `docs/` directory is the MkDocs source. Build or serve it with:

```bash
uv run mkdocs build
uv run mkdocs serve
```

The `scripts/` directory contains support utilities, including:

- Account-generation benchmarks
- Fixture update helpers
- Local CI matrix runner
- Release tag/version checks

## Practical Change Guide

When changing ledger object generation, start in the object-specific module, then
check `generate_ledger.ledger` to see how it is included in the full pipeline.
Tests usually belong in `tests/lib/`, with one CLI or integration test added only
when the public behavior changes.

When changing CLI behavior, start in `generate_ledger.cli.*` and keep parsing
logic in `generate_ledger.cli.parsers` or `shared_options` when it is shared
between root `gen` and `gen ledger`.

When changing network output, check both `generate_ledger.xrpld_cfg` and
`generate_ledger.compose`, then run a smoke test if Docker behavior changed.
