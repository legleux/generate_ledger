# generate_ledger

Generate custom XRPL genesis ledgers and complete test network environments — accounts, trustlines, AMM pools, validator configs, and docker-compose — in seconds.

## Quickstart

```bash
git clone https://github.com/legleux/generate_ledger.git
cd generate_ledger
uv sync
uv run gen ledger --accounts 10 -o ./out        # just a ledger
uv run gen auto --accounts 50 -v 5 -o ./testnet  # ledger + validators + docker-compose
```

Output: `ledger.json`, `accounts.json`, validator configs, and `docker-compose.yml` — ready to boot a test network.

## Performance

### Full `ledger.json` Generation (accounts only, ed25519)

| Accounts | CPU (PyNaCl) | GPU (CuPy) | Speedup | File size |
|----------|-------------|------------|---------|-----------|
| 1,000 | 1.5s | 2.2s | 0.7x | 342 KB |
| 10,000 | 2.0s | 2.4s | 0.8x | 3.3 MB |
| 100,000 | 8.0s | 3.6s | **2.2x** | 33 MB |
| 250,000 | 16.4s | 5.6s | **2.9x** | 82 MB |
| 500,000 | 31.6s | 8.7s | **3.6x** | 164 MB |
| 1,000,000 | 63.6s | 15.6s | **4.1x** | 327 MB |

CPU time scales linearly (~63ms per 1,000 accounts). GPU time is sub-linear,  kernel launch overhead is fixed, so the per-account cost drops at scale. GPU crossover is around 50k accounts.

> Benchmarked on 16-core AMD 5950X + RTX 5090. At 1M accounts the bottleneck is JSON serialization + disk I/O, not account generation (GPU generates 1M accounts in ~2s).

### Crypto Backend Performance

| Algorithm | Backend | Rate | vs. fallback |
|-----------|---------|------|--------------|
| ed25519 | CuPy/CUDA (GPU) | **~485,000/sec** | ~6,000x |
| ed25519 | PyNaCl (libsodium) | **~22,500/sec** | 279x |
| secp256k1 | coincurve (libsecp256k1) | ~15,000/sec | 250x |
| secp256k1 | fastecdsa (GMP) | 878/sec | 14x |
| either | xrpl-py (fallback) | 60–80/sec | 1x |

### Backend Tiers

Backends are tiered — everything works out of the box with just `xrpl-py`, and gets faster with optional dependencies:

| Tier | Dependencies | Install | What you get |
|------|-------------|---------|--------------|
| **Default** | xrpl-py (included) | `uv sync` | ~60–80 accounts/sec, no extra deps |
| **Fast** | PyNaCl, coincurve | `uv sync --group fast` | ~22k/sec ed25519, ~15k/sec secp256k1 |
| **GPU** | CuPy, CUDA toolkit wheels | `uv sync --group gpu` | ~580k/sec ed25519 (requires NVIDIA GPU) |

All tiers fall back gracefully — if a backend isn't installed, the next tier down is used automatically.

#### GPU setup

The `gpu` dependency group installs CuPy and the CUDA toolkit as pre-built pip wheels — no system CUDA install needed. Just an NVIDIA GPU with drivers.

```bash
uv sync --group gpu
uv run pytest  # GPU tests run automatically
```

`CUDA_PATH` is auto-detected from the installed `nvidia-cuda-nvcc` wheel. GPU tests skip gracefully when the GPU group isn't installed or no GPU is available.

## Install

```bash
pip install generate-ledger
```

Or from source:

```bash
git clone https://github.com/emel/generate_ledger.git
cd generate_ledger
uv sync                # xrpl-py backends only
uv sync --group fast   # + PyNaCl, coincurve
uv sync --group gpu    # + CuPy, CUDA toolkit
```

## Quick Start

```bash
# Generate a complete test environment (ledger + validators + docker-compose)
gen auto --accounts 50 --validators 5 --output-dir ./testnet

# Generate just a ledger
gen ledger --accounts 10 --output-dir ./my-ledger

# Generate with trustlines and AMM pools
gen ledger --accounts 50 --output-dir ./testnet \
  -t "0:1:USD:1000000000" \
  -a "XRP:USD:0:1000000000000:1000000:500:0"
```

## Usage

### Generate a Complete Environment

```bash
gen auto --accounts 100 --validators 5 --output-dir ./testnet
```

This creates:
- `ledger.json` — Genesis ledger with accounts, trustlines, AMM pools, and amendments
- `accounts.json` — Account credentials (addresses, seeds, keys)
- `volumes/val0/rippled.cfg` ... `valN/rippled.cfg` — Validator configurations with UNL
- `docker-compose.yml` — Ready-to-run Docker deployment

`gen auto` supports all ledger options (gateways, AMM, trustlines, amendments, fees) plus:

| Option | Default | Description |
|--------|---------|-------------|
| `--validators` / `-v` | 5 | Number of validator nodes |
| `--peer-port` | 51235 | Port used in `[ips_fixed]` entries |
| `--amendment-majority-time` | — | Override amendment majority time (e.g. `2 minutes`) |

```bash
# Full environment with gateways and custom fees
gen auto --accounts 200 -v 5 -o ./testnet \
  --gateways 4 --assets-per-gateway 3 --gateway-coverage 0.8 \
  --base-fee 10 --reserve-base 200000 --reserve-inc 50000
```

### Generate Ledger Only

```bash
gen ledger --accounts 100 --output-dir ./output
```

### Trustlines

```bash
# Explicit trustline: account 0 trusts account 1 for USD, limit 1B
gen ledger --accounts 10 --output-dir ./out -t "0:1:USD:1000000000"

# Random trustlines (star topology from account 0)
gen ledger --accounts 100 --output-dir ./out --num-trustlines 20

# Multiple currencies
gen ledger --accounts 50 --output-dir ./out --currencies USD,EUR,JPY --num-trustlines 10
```

### AMM Pools

```bash
# XRP/USD pool: issuer=account 0, XRP deposit=1T drops, USD deposit=1M, LP tokens=500, fee=0
gen ledger --accounts 10 --output-dir ./out \
  -t "0:1:USD:1000000000" \
  -a "XRP:USD:0:1000000000000:1000000:500:0"
```

### Gateways

Gateway accounts issue assets and create a realistic trustline topology across your test network.

```bash
# 4 gateways, each issuing 3 assets, 80% of accounts get trustlines
gen ledger --accounts 100 --output-dir ./out \
  --gateways 4 --assets-per-gateway 3 --gateway-coverage 0.8
```

| Option | Default | Description |
|--------|---------|-------------|
| `--gateways N` | 0 | Number of gateway accounts (first N accounts become gateways) |
| `--assets-per-gateway N` | 4 | Unique assets each gateway issues |
| `--gateway-currencies` | USD,EUR,GBP,JPY,BTC,ETH,CNY,MXN,CAD,AUD | Currency pool (distributed round-robin) |
| `--gateway-coverage` | 0.5 | Fraction of non-gateway accounts that receive trustlines (0.0–1.0) |
| `--gateway-connectivity` | 0.5 | Fraction of gateways each account connects to (0.0–1.0) |
| `--gateway-seed` | — | RNG seed for reproducible topology |

### MPT (Multi-Purpose Tokens)

```bash
# MPT issuance: issuer=account 0, sequence=1
gen ledger --accounts 10 --output-dir ./out --mpt "0:1"
```

Format: `issuer:sequence[:max_amount[:flags[:asset_scale]]]`. Requires the `MPTokensV1` amendment (develop branch).

### Amendment Profiles

```bash
# Curated mainnet amendments (default)
gen ledger --accounts 10 --amendment-profile release

# Parse from a local rippled repo's features.macro
gen ledger --accounts 10 --amendment-profile develop \
  --amendment-source /path/to/rippled/include/xrpl/protocol/detail/features.macro

# Per-amendment overrides
gen ledger --accounts 10 --enable-amendment SomeFeature --disable-amendment Clawback
```

The `--amendment-source` option accepts a path to any `features.macro` file, so you can point it at your local rippled checkout to pick up amendments from any branch.

**Important distinction:** `features.macro` defines what amendments a rippled build *supports* — not what is *enabled on a live network*. Amendments are enabled on mainnet only after reaching 80% validator consensus, which can lag weeks or months behind a release. The `release` profile queries a mainnet node (falling back to a bundled snapshot) to get the actual enabled set. The `develop` profile enables all supported amendments, matching the behavior of a freshly started test network.

### Fee Configuration

```bash
gen ledger --accounts 10 --base-fee 10 --reserve-base 200000 --reserve-inc 50000
```

| Option | Default | Description |
|--------|---------|-------------|
| `--base-fee` | 121 | Base transaction fee (drops) |
| `--reserve-base` | 2000000 | Account reserve base (drops) |
| `--reserve-inc` | 666 | Owner reserve increment per object (drops) |

### Algorithm Selection

```bash
gen ledger --accounts 1000 --algo ed25519    # Fast (default, ~22k/sec with PyNaCl)
gen ledger --accounts 1000 --algo secp256k1  # Slower (~60/sec with xrpl-py fallback)
```

### Subcommands

#### `gen rippled` — Generate Validator Configs

Writes per-node `rippled.cfg` files with UNL, voting stanzas, and peer discovery.

```bash
gen rippled -v 5 -b ./testnet/volumes
```

| Option | Default | Description |
|--------|---------|-------------|
| `--validators` / `-v` | 5 | Number of validator nodes |
| `--base-dir` / `-b` | `testnet/volumes` | Output directory for node subdirs |
| `--template-path` / `-t` | built-in | Path to base `rippled.cfg` template |
| `--peer-port` | 51235 | Port for `[ips_fixed]` entries |
| `--reference-fee` | 10 | Voting: reference fee (drops) |
| `--account-reserve` | 200000 | Voting: account reserve (drops) |
| `--owner-reserve` | 1000000 | Voting: owner reserve (drops) |
| `--keygen` | `xrpl` | Key generation backend (`xrpl` or `docker`) |
| `--amendment-majority-time` | — | Override amendment majority time |

#### `gen compose write` — Generate Docker Compose

Writes a `docker-compose.yml` for the validator cluster.

```bash
gen compose write -v 5 -o ./testnet/docker-compose.yml
```

| Option | Default | Description |
|--------|---------|-------------|
| `--validators` / `-v` | — | Number of validator nodes |
| `--output-file` / `-o` | — | Output file path |
| `--validator-image` | — | Docker image for validators |
| `--validator-version` | — | Image version tag |
| `--hubs` | — | Number of hub nodes |

## Validator Configuration

Set this in `[voting]` to preserve reserve settings after the flag ledger:

```ini
[voting]
reference_fee = 1
account_reserve = 1000000
owner_reserve = 200000
```

This is handled automatically by `gen auto` and `gen validators`.

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
uv run scripts/bench_accounts.py --accounts 10000 --algo ed25519 --mode seq
```

## License

MIT
