# Quick Start

## Installation

```bash
git clone https://github.com/legleux/generate_ledger.git
cd generate_ledger
uv sync                # default (xrpl-py backends only)
uv sync --group fast   # + PyNaCl, coincurve (recommended)
uv sync --group gpu    # + CuPy, CUDA toolkit
```

## First Commands

### Generate a Complete Test Environment

```bash
gen auto --accounts 50 --validators 5 --output-dir ./testnet
```

This creates everything needed to boot a test network:

- `ledger.json` -- Genesis ledger with 50 pre-funded accounts and enabled amendments
- `accounts.json` -- Account credentials (addresses, seeds, keys)
- `volumes/val0/rippled.cfg` through `valN/rippled.cfg` -- Validator configurations with UNL
- `docker-compose.yml` -- Docker deployment ready to `docker compose up`

### Generate Just a Ledger

```bash
gen ledger --accounts 10 --output-dir ./my-ledger
```

### Add Trustlines and AMM Pools

```bash
gen ledger --accounts 50 --output-dir ./out \
  -t "0:1:USD:1000000000" \
  -a "XRP:USD:0:1000000000000:1000000:500:0"
```

### Add Gateway Topology

```bash
gen ledger --accounts 100 --output-dir ./out \
  --gateways 4 --assets-per-gateway 3 --gateway-coverage 0.8
```

## Algorithm Selection

By default, accounts are generated using the ed25519 algorithm with PyNaCl for maximum speed. You can switch to secp256k1 if needed:

```bash
gen ledger --accounts 1000 --algo ed25519    # ~22k/sec with PyNaCl (default)
gen ledger --accounts 1000 --algo secp256k1  # ~60/sec with xrpl-py fallback
```

## What Next

- See the [CLI Reference](cli.md) for all available options
- Use `generate_ledger` [as a library](library.md) in your Python code
- Learn about [amendment profiles](amendments.md) to control which amendments are enabled
