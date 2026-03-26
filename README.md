# generate_ledger

Generate custom XRPL genesis ledgers and complete test network environments — accounts, trustlines, AMM pools, validator configs, and docker-compose — in seconds.

## First order of business, rename

- `ledgen` - My initial thought but maybe prone to typos aad or misunderstanding?
- `xrpl-genesis` - Genesis ledger is automatic, `xrpl-pre-genesis` more accurate?
- `ledgectl` - Doesn't really control.
- `ledgergen` - Boring.
- `ledgerforge` - Heavy

## Quickstart

```bash
git clone https://github.com/legleux/generate_ledger.git
cd generate_ledger
uv sync
uv run gen
cd testnet && docker compose up
```

Output: `ledger.json`, `accounts.json`, validator configs (`xrpld.cfg`), and `docker-compose.yml`. In under a minute you'll have a running XRPL test network.

```bash
# Just a ledger
uv run gen ledger --accounts 10 --output-dir ./my-ledger

# With trustlines and AMM pools
uv run gen ledger --accounts 50 --output-dir ./testnet \
  --trustline "0:1:USD:1000000000" \
  --amm-pool "XRP:USD:0:1000000000000:1000000:500:0"
```

## Performance

### Full `ledger.json` Generation (accounts only, ed25519)

| Accounts  | CPU (PyNaCl) | GPU (CuPy) | Speedup  | File size |
| --------- | ------------ | ---------- | -------- | --------- |
| 1,000     | 0.3s         | 0.7s       | 0.4x     | 0.3 MB    |
| 10,000    | 0.6s         | 0.1s       | **6x**   | 3.3 MB    |
| 100,000   | 5.3s         | 0.7s       | **7.6x** | 33 MB     |
| 250,000   | 13.3s        | 2.2s       | **6x**   | 82 MB     |
| 500,000   | 26.0s        | 3.1s       | **8.4x** | 163 MB    |
| 1,000,000 | 52.1s        | 6.1s       | **8.5x** | 326 MB    |

CPU time scales linearly (~52ms per 1,000 accounts). GPU time is sub-linear — kernel launch overhead is fixed, so the per-account cost drops at scale. GPU crossover is around 5k accounts.

> Benchmarked on 16-core AMD 5950X + RTX 5090, Python 3.14. At 1M accounts the bottleneck is JSON serialization, not account generation (GPU generates 1M accounts in ~2s).

### Crypto Backend Performance

| Algorithm | Backend                  | Rate             | vs. fallback |
| --------- | ------------------------ | ---------------- | ------------ |
| ed25519   | CuPy/CUDA (GPU)          | **~280,000/sec** | ~4,000x      |
| ed25519   | PyNaCl + multiprocessing | **~88,000/sec**  | ~1,200x      |
| ed25519   | PyNaCl (single-core)     | **~25,000/sec**  | 350x         |
| secp256k1 | coincurve (single-core)  | ~7,400/sec       | 100x         |
| either    | xrpl-py (fallback)       | 60–80/sec        | 1x           |

Multiprocessing kicks in automatically above 50k accounts. Below that, single-core is faster due to process spawn overhead.

### Backend Tiers

Backends are tiered and fall back gracefully:

| Tier        | Dependencies              | Install               | What you get                                 |
| ----------- | ------------------------- | --------------------- | -------------------------------------------- |
| **Default** | PyNaCl, coincurve         | `uv sync`             | ~25-88k/sec ed25519 (auto-scales with cores) |
| **Minimal** | xrpl-py only              | _(auto-fallback)_     | ~60–80 accounts/sec, no native deps          |
| **GPU**     | CuPy, CUDA toolkit wheels | `uv sync --group gpu` | ~280k/sec ed25519 (requires NVIDIA GPU)      |

#### GPU setup

The `gpu` dependency group installs CuPy and the CUDA toolkit as pre-built pip wheels — no system CUDA install needed. Just an NVIDIA GPU with drivers.

```bash
uv sync --group gpu
uv run gen --gpu --accounts 100000
```

`CUDA_PATH` is auto-detected from the installed `nvidia-cuda-nvcc` wheel. GPU tests skip gracefully when the GPU group isn't installed or no GPU is available.

## Install

```bash
pip install generate-ledger
```

Or from source:

```bash
git clone https://github.com/legleux/generate_ledger.git
cd generate_ledger
uv sync                # includes fast crypto backends (PyNaCl, coincurve)
uv sync --group gpu    # + CuPy, CUDA toolkit (optional, requires NVIDIA GPU)
```

## CLI Help

```bash
uv run gen --help
uv run gen ledger --help
uv run gen xrpld --help
```

## Usage

### Generate a Complete Environment

```bash
uv run gen --accounts 100 --validators 5 --output-dir ./testnet
```

This creates:

- `ledger.json` — Genesis ledger with accounts, trustlines, AMM pools, and amendments
- `accounts.json` — Account credentials (addresses, seeds, keys)
- `volumes/val0/xrpld.cfg` ... `valN/xrpld.cfg` — Validator configurations with UNL
- `docker-compose.yml` — Ready-to-run Docker deployment

Bare `gen` supports all ledger options (gateways, AMM, trustlines, amendments, fees) plus:

| Option                      | Default                  | Description                                            |
| --------------------------- | ------------------------ | ------------------------------------------------------ |
| `--validators` / `-v`       | 5                        | Number of validator nodes                              |
| `--peer-port`               | 51235                    | Port used in `[ips_fixed]` entries                     |
| `--amendment-majority-time` | —                        | Override amendment majority time (e.g. `2 minutes`)    |
| `--log-level`               | `info`                   | xrpld log level (trace/debug/info/warning/error/fatal) |
| `--image`                   | `rippleci/xrpld:develop` | Docker image for xrpld nodes                           |

```bash
# Full environment with gateways and custom fees
uv run gen --accounts 200 --validators 5 --output-dir ./testnet \
  --gateways 4 --assets-per-gateway 3 --gateway-coverage 0.8 \
  --base-fee 10 --reserve-base 200000 --reserve-inc 50000
```

### Generate Ledger Only

```bash
uv run gen ledger --accounts 100 --output-dir ./output
```

### Trustlines

```bash
# Explicit trustline: account 0 trusts account 1 for USD, limit 1B
uv run gen ledger --accounts 10 --output-dir ./out --trustline "0:1:USD:1000000000"

# Random trustlines (star topology from account 0)
uv run gen ledger --accounts 100 --output-dir ./out --num-trustlines 20

# Multiple currencies
uv run gen ledger --accounts 50 --output-dir ./out --currencies USD,EUR,JPY --num-trustlines 10
```

### AMM Pools

```bash
# XRP/USD pool: issuer=account 0, XRP deposit=1T drops, USD deposit=1M, LP tokens=500, fee=0
uv run gen ledger --accounts 10 --output-dir ./out \
  --trustline "0:1:USD:1000000000" \
  --amm-pool "XRP:USD:0:1000000000000:1000000:500:0"
```

### Gateways

Gateway accounts issue assets and create a realistic trustline topology across your test network.

```bash
# 4 gateways, each issuing 3 assets, 80% of accounts get trustlines
uv run gen ledger --accounts 100 --output-dir ./out \
  --gateways 4 --assets-per-gateway 3 --gateway-coverage 0.8
```

| Option                   | Default                                 | Description                                                        |
| ------------------------ | --------------------------------------- | ------------------------------------------------------------------ |
| `--gateways N`           | 0                                       | Number of gateway accounts (first N accounts become gateways)      |
| `--assets-per-gateway N` | 4                                       | Unique assets each gateway issues                                  |
| `--gateway-currencies`   | USD,EUR,GBP,JPY,BTC,ETH,CNY,MXN,CAD,AUD | Currency pool (distributed round-robin)                            |
| `--gateway-coverage`     | 0.5                                     | Fraction of non-gateway accounts that receive trustlines (0.0–1.0) |
| `--gateway-connectivity` | 0.5                                     | Fraction of gateways each account connects to (0.0–1.0)            |
| `--gateway-seed`         | —                                       | RNG seed for reproducible topology                                 |

### MPT (Multi-Purpose Tokens)

```bash
# MPT issuance: issuer=account 0, sequence=1
uv run gen ledger --accounts 10 --output-dir ./out --mpt "0:1"
```

Format: `issuer:sequence[:max_amount[:flags[:asset_scale]]]`. Requires the `MPTokensV1` amendment (develop branch).

### Amendment Profiles

```bash
# Curated mainnet amendments (default)
uv run gen ledger --accounts 10 --amendment-profile release

# Parse from a local xrpld repo's features.macro
uv run gen ledger --accounts 10 --amendment-profile develop \
  --amendment-source /path/to/xrpld/include/xrpl/protocol/detail/features.macro

# Per-amendment overrides
uv run gen ledger --accounts 10 --enable-amendment SomeFeature --disable-amendment Clawback
```

The `--amendment-source` option accepts a path to any `features.macro` file, so you can point it at your local xrpld checkout to pick up amendments from any branch.

**Important distinction:** `features.macro` defines what amendments an xrpld build _supports_ — not what is _enabled on a live network_. Amendments are enabled on mainnet only after reaching 80% validator consensus, which can lag weeks or months behind a release. The `release` profile queries a mainnet node (falling back to a bundled snapshot) to get the actual enabled set. The `develop` profile enables all supported amendments, matching the behavior of a freshly started test network.

### Fee Configuration

```bash
uv run gen ledger --accounts 10 --base-fee 10 --reserve-base 200000 --reserve-inc 50000
```

| Option           | Default | Description                                |
| ---------------- | ------- | ------------------------------------------ |
| `--base-fee`     | 121     | Base transaction fee (drops)               |
| `--reserve-base` | 2000000 | Account reserve base (drops)               |
| `--reserve-inc`  | 666     | Owner reserve increment per object (drops) |

### Subcommands

#### `gen xrpld` — Generate Validator Configs

Writes per-node `xrpld.cfg` files with UNL, voting stanzas, and peer discovery.

```bash
uv run gen xrpld --validators 5 --base-dir ./testnet/volumes
```

| Option                      | Default           | Description                                            |
| --------------------------- | ----------------- | ------------------------------------------------------ |
| `--validators` / `-v`       | 5                 | Number of validator nodes                              |
| `--base-dir` / `-b`         | `testnet/volumes` | Output directory for node subdirs                      |
| `--template-path` / `-t`    | built-in          | Path to base `xrpld.cfg` template                      |
| `--peer-port`               | 51235             | Port for `[ips_fixed]` entries                         |
| `--reference-fee`           | 10                | Voting: reference fee (drops)                          |
| `--account-reserve`         | 200000            | Voting: account reserve (drops)                        |
| `--owner-reserve`           | 1000000           | Voting: owner reserve (drops)                          |
| `--keygen`                  | `xrpl`            | Key generation backend (`xrpl` or `docker`)            |
| `--log-level`               | `info`            | xrpld log level (trace/debug/info/warning/error/fatal) |
| `--amendment-majority-time` | —                 | Override amendment majority time                       |

## Validator Configuration

Set this in `[voting]` to preserve reserve settings after the flag ledger:

```ini
[voting]
reference_fee = 1
account_reserve = 1000000
owner_reserve = 200000
```

This is handled automatically by `gen` when generating the full environment.

## Development

```bash
# Run tests (GPU tests skip automatically if GPU group not installed)
uv run pytest

# Run tests with GPU backend
uv sync --group gpu
uv run pytest

# Lint
uv run ruff check .

# Build locally (sdist + wheel → dist/)
uv build

# Run benchmarks (see scripts/README.md)
uv run scripts/bench_accounts.py --accounts 10000 --mode seq
```
