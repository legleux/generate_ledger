# generate_ledger

Generate custom XRPL genesis ledgers and complete test network environments — accounts, trustlines, AMM pools, validator configs, and docker-compose — in seconds.

## Performance

With the default ed25519 algorithm and PyNaCl backend:

| Scenario | Accounts | Trustlines | AMM | Validators | Time |
|----------|----------|------------|-----|------------|------|
| Ledger only | 5,000 | — | — | — | **1.6s** |
| Ledger only | 10,000 | — | — | — | **1.5s** |
| Ledger + trustlines | 1,000 | 10 | — | — | **1.2s** |
| Ledger + trustlines + AMM | 5,000 | 50 | 1 pool | — | **2.3s** |
| Full environment (`gen auto`) | 5,000 | — | — | 5 | **1.2s** |

> Account generation: **~22,500 accounts/sec** (ed25519 + PyNaCl) vs ~60/sec with the xrpl-py fallback — a **279x speedup**. See [scripts/README.md](scripts/README.md) for detailed crypto backend benchmarks.

### Crypto Backend Performance

| Algorithm | Backend | Rate | vs. fallback |
|-----------|---------|------|--------------|
| ed25519 | PyNaCl (libsodium) | **22,568/sec** | 279x |
| secp256k1 | coincurve (libsecp256k1) | ~15,000/sec | 250x |
| secp256k1 | fastecdsa (GMP) | 878/sec | 14x |
| either | xrpl-py (fallback) | 60–80/sec | 1x |

PyNaCl is included by default. Install `coincurve` or `fastecdsa` for fast secp256k1.

## Install

```bash
pip install generate-ledger
```

Or from source:

```bash
git clone https://github.com/emel/generate_ledger.git
cd generate_ledger
uv sync
```

## Quick Start

```bash
# Generate a complete test environment (ledger + validators + docker-compose)
gen auto --accounts 50 --validators 5 --output-dir ./testnet

# Generate just a ledger
gen ledger --accounts 10 --output ./my-ledger

# Generate with trustlines and AMM pools
gen ledger -n 50 -o ./testnet \
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

### Generate Ledger Only

```bash
gen ledger -n 100 -o ./output
```

### Trustlines

```bash
# Explicit trustline: account 0 trusts account 1 for USD, limit 1B
gen ledger -n 10 -o ./out -t "0:1:USD:1000000000"

# Random trustlines (star topology from account 0)
gen ledger -n 100 -o ./out --num-trustlines 20

# Multiple currencies
gen ledger -n 50 -o ./out --currencies USD,EUR,JPY --num-trustlines 10
```

### AMM Pools

```bash
# XRP/USD pool: issuer=account 0, XRP deposit=1T drops, USD deposit=1M, LP tokens=500, fee=0
gen ledger -n 10 -o ./out \
  -t "0:1:USD:1000000000" \
  -a "XRP:USD:0:1000000000000:1000000:500:0"
```

### Amendment Profiles

```bash
# Curated release amendments (default)
gen ledger -n 10 --amendment-profile release

# Parse from rippled source
gen ledger -n 10 --amendment-profile develop --amendment-source /path/to/features.macro

# Per-amendment overrides
gen ledger -n 10 --enable-amendment SomeFeature --disable-amendment Clawback
```

### Algorithm Selection

```bash
gen ledger -n 1000 --algo ed25519    # Fast (default, ~22k/sec with PyNaCl)
gen ledger -n 1000 --algo secp256k1  # Slower (~60/sec with xrpl-py fallback)
```

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
# Run tests
pytest

# Lint
ruff check .

# Run benchmarks (see scripts/README.md)
uv run scripts/bench_accounts.py -n 10000 --algo ed25519 --mode seq
```

## License

MIT
