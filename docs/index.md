# generate_ledger

Generate custom XRPL genesis ledgers and complete test network environments in seconds.

## What It Does

`generate_ledger` solves three problems for XRPL developers who need a private test network:

1. **Pre-generate a genesis ledger** -- Produce a `ledger.json` that [xrpld](https://github.com/XRPLF/rippled) loads at startup with an initial state ready to go, eliminating the need to submit and process transactions to set up accounts, trustlines, and other objects. This dramatically shortens iteration time for development and testing.

2. **Generate xrpld configuration files** -- Create per-node `xrpld.cfg` files that define the network: validator identities, peer connections, UNL (Unique Node List), amendment voting, and economic parameters (fees, reserves).

3. **Generate a Docker Compose file** -- Produce a `docker-compose.yml` that realizes the network as a set of containers, ready to `docker compose up`.

A single command (`uv run gen`) produces all three.

### Ledger Object Types

The genesis ledger can include:

| Object                     | XRPL Type                     | Description                                                       |
| -------------------------- | ----------------------------- | ----------------------------------------------------------------- |
| **Accounts**               | `AccountRoot`                 | Pre-funded accounts with keypairs (ed25519 or secp256k1)          |
| **Trustlines**             | `RippleState`                 | Explicit, random, or gateway-topology trustlines between accounts |
| **Gateway topology**       | `RippleState`                 | Star/mesh trustline networks from issuer accounts                 |
| **AMM pools**              | `AMM` + `AccountRoot`         | Automated Market Maker pools with LP tokens and asset trustlines  |
| **Amendments**             | `Amendments`                  | Enabled amendments (release, develop, or custom profile)          |
| **Directory nodes**        | `DirectoryNode`               | Per-account ownership directories (auto-generated)                |
| **MPT** _(develop branch)_ | `MPTokenIssuance` + `MPToken` | Multi-Purpose Tokens (issuances and holder tokens)                |

### Output Files

| File                      | Description                                                 |
| ------------------------- | ----------------------------------------------------------- |
| `ledger.json`             | Genesis ledger with all objects above                       |
| `accounts.json`           | Account credentials (addresses, seeds, public/private keys) |
| `volumes/val*/xrpld.cfg`  | Per-validator xrpld configuration                           |
| `volumes/xrpld/xrpld.cfg` | Non-validator hub node configuration                        |
| `docker-compose.yml`      | Docker deployment for the full network                      |

## Performance

With the default ed25519 algorithm and PyNaCl backend:

| Scenario                  | Accounts | Trustlines | AMM    | Validators | Time     |
| ------------------------- | -------- | ---------- | ------ | ---------- | -------- |
| Ledger only               | 5,000    | --         | --     | --         | **1.6s** |
| Ledger only               | 10,000   | --         | --     | --         | **1.5s** |
| Ledger + trustlines       | 1,000    | 10         | --     | --         | **1.2s** |
| Ledger + trustlines + AMM | 5,000    | 50         | 1 pool | --         | **2.3s** |
| Full environment (`gen`)  | 5,000    | --         | --     | 5          | **1.2s** |

Account generation runs at approximately **22,500 accounts/sec** with ed25519 + PyNaCl, compared to ~60/sec with the xrpl-py fallback -- a 279x speedup.

## Crypto Backend Tiers

Backends are tiered and fall back gracefully:

| Tier        | Dependencies              | Install               | What you get                            |
| ----------- | ------------------------- | --------------------- | --------------------------------------- |
| **Default** | PyNaCl, coincurve         | `uv sync`             | ~22k/sec ed25519, ~15k/sec secp256k1    |
| **Minimal** | xrpl-py only              | _(auto-fallback)_     | ~60-80 accounts/sec, no native deps     |
| **GPU**     | CuPy, CUDA toolkit wheels | `uv sync --group gpu` | ~580k/sec ed25519 (requires NVIDIA GPU) |

All tiers fall back gracefully -- if a backend is not installed, the next tier down is used automatically.

## Next Steps

- [Quick Start](quickstart.md) -- Install and generate your first ledger
- [CLI Reference](cli.md) -- Full command documentation
- [Library API](library.md) -- Use `generate_ledger` as a Python library
- [Amendments](amendments.md) -- How amendment profiles work
- [Development](development.md) -- Contributing, running tests, GPU setup
