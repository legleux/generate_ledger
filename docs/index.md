# generate_ledger

Generate custom XRPL genesis ledgers and complete test network environments -- accounts, trustlines, AMM pools, validator configs, and docker-compose -- in seconds.

## What It Does

`generate_ledger` produces `ledger.json` files that bootstrap [rippled](https://github.com/XRPLF/rippled) nodes with pre-funded accounts and enabled amendments. A single command gives you everything needed to spin up a private XRPL test network:

- **`ledger.json`** -- Genesis ledger with accounts, trustlines, AMM pools, and amendments
- **`accounts.json`** -- Account credentials (addresses, seeds, keys)
- **Validator configs** -- Per-node `rippled.cfg` files with UNL and voting stanzas
- **`docker-compose.yml`** -- Ready-to-run Docker deployment

## Performance

With the default ed25519 algorithm and PyNaCl backend:

| Scenario | Accounts | Trustlines | AMM | Validators | Time |
|----------|----------|------------|-----|------------|------|
| Ledger only | 5,000 | -- | -- | -- | **1.6s** |
| Ledger only | 10,000 | -- | -- | -- | **1.5s** |
| Ledger + trustlines | 1,000 | 10 | -- | -- | **1.2s** |
| Ledger + trustlines + AMM | 5,000 | 50 | 1 pool | -- | **2.3s** |
| Full environment (`gen auto`) | 5,000 | -- | -- | 5 | **1.2s** |

Account generation runs at approximately **22,500 accounts/sec** with ed25519 + PyNaCl, compared to ~60/sec with the xrpl-py fallback -- a 279x speedup.

## Crypto Backend Tiers

Backends are tiered -- everything works out of the box with just xrpl-py, and gets faster with optional dependencies:

| Tier | Dependencies | Install | What you get |
|------|-------------|---------|--------------|
| **Default** | xrpl-py (included) | `uv sync` | ~60-80 accounts/sec, no extra deps |
| **Fast** | PyNaCl, coincurve | `uv sync --group fast` | ~22k/sec ed25519, ~15k/sec secp256k1 |
| **GPU** | CuPy, CUDA toolkit wheels | `uv sync --group gpu` | ~580k/sec ed25519 (requires NVIDIA GPU) |

All tiers fall back gracefully -- if a backend is not installed, the next tier down is used automatically.

## Next Steps

- [Quick Start](quickstart.md) -- Install and generate your first ledger
- [CLI Reference](cli.md) -- Full command documentation
- [Library API](library.md) -- Use `generate_ledger` as a Python library
- [Amendments](amendments.md) -- How amendment profiles work
- [Development](development.md) -- Contributing, running tests, GPU setup
