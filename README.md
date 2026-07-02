# generate_ledger

`generate_ledger` creates XRPL genesis ledgers and private test network scaffolding.
It can produce funded accounts, trustlines, gateway-style issued-asset topology,
AMM pools, MPT objects, Sponsorship objects, amendment entries, `xrpld.cfg` files, and a
`docker-compose.yml` that can boot a local XRPL network.

The default command is intentionally broad:

```bash
uv run gen
```

That writes a complete `testnet/` directory with:

- `ledger.json`: genesis ledger state for `xrpld`
- `accounts.json`: generated account addresses and seeds
- `volumes/val*/xrpld.cfg`: validator configuration and UNL data
- `volumes/xrpld/xrpld.cfg`: non-validator node configuration
- `docker-compose.yml`: container definition for the generated network

By default, bare `gen` creates 100 regular accounts, 5 validators, and 1
non-validator `xrpld` node.

## Quick Start

```bash
git clone https://github.com/legleux/generate_ledger.git
cd generate_ledger
uv sync
uv run gen
cd testnet
docker compose up -d
```

Verify a validator:

```bash
curl -s localhost:5005 -d '{"method": "server_info"}' | jq .result.info.server_state
```

Generate only a ledger:

```bash
uv run gen ledger --accounts 10 --output-dir ./my-ledger
```

Generate a ledger with trustlines and an AMM pool:

```bash
uv run gen ledger --accounts 50 --output-dir ./out \
  --trustline "0:1:USD:1000000000" \
  --amm-pool "XRP:USD:0:1000000000000:1000000:500:0"
```

## Installation

From PyPI:

```bash
pip install generate-ledger
```

From source:

```bash
git clone https://github.com/legleux/generate_ledger.git
cd generate_ledger
uv sync
```

Optional dependency groups:

```bash
uv sync --group fast   # PyNaCl and coincurve crypto backends
uv sync --group gpu    # CuPy/CUDA account generation backend
```

## Main Workflows

### Full Local Network

Use the root command when you want ledger state, `xrpld` configuration, and Docker
Compose output in one pass:

```bash
uv run gen --accounts 200 --validators 5 --output-dir ./testnet \
  --gateways 4 --assets-per-gateway 3 --gateway-coverage 0.8
```

This is the fastest path for integration tests, demos, and local protocol work.

### Ledger Only

Use `gen ledger` when another tool will run the network or when you only need the
genesis state:

```bash
uv run gen ledger --accounts 100 --output-dir ./ledger-out
```

Common additions:

```bash
# Random trustlines
uv run gen ledger --accounts 100 --num-trustlines 20 --currencies USD,EUR

# Gateway topology
uv run gen ledger --accounts 100 --gateways 4 --assets-per-gateway 3

# Multi-Purpose Token issuance
uv run gen ledger --accounts 10 --mpt "0:1"

# Sponsorship relationship
uv run gen ledger --accounts 10 --sponsorship "0:1:1000000:10:5" --enable-amendment Sponsor
```

### xrpld Config Only

Use `gen xrpld` when you already have ledger state and only need node
configuration:

```bash
uv run gen xrpld --validators 5 --base-dir ./testnet/volumes
```

## CLI Reference

```bash
uv run gen --help
uv run gen ledger --help
uv run gen xrpld --help
```

High-value options:

| Option                | Applies to     | Purpose                                                                       |
| --------------------- | -------------- | ----------------------------------------------------------------------------- |
| `--accounts`          | root, `ledger` | Number of generated regular accounts                                          |
| `--validators`        | root, `xrpld`  | Number of validator nodes                                                     |
| `--output-dir`        | root, `ledger` | Output directory                                                              |
| `--trustline`         | root, `ledger` | Explicit trustline: `account1:account2:currency:limit`                        |
| `--num-trustlines`    | `ledger`       | Generate random trustlines                                                    |
| `--gateways`          | root, `ledger` | Make the first N accounts issued-asset gateways                               |
| `--amm-pool`          | root, `ledger` | AMM pool: `asset1:asset2:amount1:amount2[:fee[:creator]]`                     |
| `--mpt`               | `ledger`       | MPT issuance: `issuer:sequence[:max_amount[:flags[:scale[:fee[:metadata]]]]]` |
| `--sponsorship`       | root, `ledger` | Sponsorship: `owner:sponsee[:fee_amount[:max_fee[:reserve_count[:flags]]]]`   |
| `--amendment-profile` | root, `ledger` | `release`, `develop`, or `custom` amendments                                  |
| `--base-fee`          | root, `ledger` | Base transaction fee in drops                                                 |
| `--reserve-base`      | root, `ledger` | Account reserve in drops                                                      |
| `--reserve-inc`       | root, `ledger` | Owner reserve increment in drops                                              |
| `--gpu`               | root, `ledger` | Use GPU account generation when available                                     |

## Python Library Usage

The package can also be used without the CLI:

```python
from generate_ledger.accounts import AccountConfig
from generate_ledger.ledger import LedgerConfig, gen_ledger_state

ledger = gen_ledger_state(
    LedgerConfig(
        account_cfg=AccountConfig(num_accounts=50, algo="ed25519"),
        amendment_profile="release",
    ),
    write_accounts=False,
)

print(len(ledger["ledger"]["accountState"]))
```

See the MkDocs library page for more examples.

## Project Layout

| Path                                    | Purpose                                                             |
| --------------------------------------- | ------------------------------------------------------------------- |
| `src/generate_ledger/cli/`              | Typer CLI entry points and spec parsers                             |
| `src/generate_ledger/accounts.py`       | Account generation and account reference resolution                 |
| `src/generate_ledger/ledger.py`         | Top-level ledger configuration and assembly pipeline                |
| `src/generate_ledger/ledger_builder.py` | Final XRPL ledger JSON construction                                 |
| `src/generate_ledger/indices.py`        | XRPL ledger index derivation helpers                                |
| `src/generate_ledger/trustlines.py`     | `RippleState` and owner directory generation                        |
| `src/generate_ledger/gateways.py`       | Gateway-issued asset topology                                       |
| `src/generate_ledger/amm.py`            | AMM object generation                                               |
| `src/generate_ledger/mpt.py`            | MPT ledger object generation                                        |
| `src/generate_ledger/sponsor.py`        | Sponsor amendment Sponsorship object generation                     |
| `src/generate_ledger/amendments.py`     | Amendment profile loading and hashing                               |
| `src/generate_ledger/xrpld_cfg.py`      | Layered `xrpld.cfg` rendering                                       |
| `src/generate_ledger/compose.py`        | Docker Compose generation                                           |
| `tests/`                                | Unit, CLI, integration, and Docker smoke tests                      |
| `docs/`                                 | MkDocs source                                                       |
| `scripts/`                              | Benchmarks, fixture updates, release helpers, and local test matrix |

## Development

```bash
# Tests
uv run pytest

# Include optional fast crypto dependencies
uv sync --group fast

# Include optional GPU dependencies
uv sync --group gpu

# Lint
uv run ruff check .

# Build package artifacts
uv build

# Build docs
uv run mkdocs build
```

Smoke tests that require Docker are marked separately:

```bash
uv run pytest -m smoke
```

## Documentation

The MkDocs site has the deeper reference material:

- `docs/index.md`: overview
- `docs/project-guide.md`: broad repository guide
- `docs/quickstart.md`: first run
- `docs/cli.md`: full CLI reference
- `docs/how-it-works.md`: XRPL object and index derivation
- `docs/library.md`: Python API usage
- `docs/amendments.md`: amendment profiles
- `docs/development.md`: contributor workflow

Serve it locally with:

```bash
uv run mkdocs serve
```
