# XRPL Account & Trustline Generation Benchmark

Benchmark script for testing parallel XRPL account generation and trustline (RippleState + DirectoryNode) object generation strategies, optimized for Python 3.13+ (including free-threaded/no-GIL builds).

## Quick Start

```bash
# Install native crypto backends (recommended)
pip install pynacl fastecdsa

# Run account benchmark
uv run scripts/bench_accounts.py -n 1000 --algo ed25519 --mode seq

# Run accounts + trustlines benchmark
uv run scripts/bench_accounts.py -n 1000 --trustlines --mode mp
```

## Usage

```
usage: bench_accounts.py [-h] -n COUNT [--mode {seq,mp,thread,hybrid,gpu}]
                         [--workers WORKERS] [--algo {secp256k1,ed25519}]
                         [--output FILE] [--quiet] [--info]
                         [--trustlines] [--topology {star,ring,mesh,random}]
                         [--currencies CURRENCIES] [--limit LIMIT]

Account Options:
  -n, --count       Number of accounts to generate
  --mode            Parallelization mode (default: seq)
  --workers         Number of workers (default: CPU count)
  --algo            Crypto algorithm (default: secp256k1)
  --output FILE     Output JSON file with results
  --quiet           Suppress progress output
  --info            Print system info and exit

Trustline Options:
  --trustlines      Enable trustline generation benchmark
  --topology        Trustline topology: star, ring, mesh, random (default: star)
  --currencies      Comma-separated currencies (default: USD)
  --limit           Trust limit (default: 1000000)
```

## Parallelization Modes

| Mode | Description |
|------|-------------|
| `seq` | Sequential (single-threaded baseline) |
| `mp` | Multiprocessing with `ProcessPoolExecutor` |
| `thread` | Threading with `ThreadPoolExecutor` (benefits from 3.13t no-GIL) |
| `hybrid` | Processes spawning thread pools |
| `gpu` | GPU acceleration (stub, falls back to mp) |

## Trustline Topologies

| Topology | Description | Pairs per currency |
|----------|-------------|-------------------|
| `star` | All accounts trust account 0 (default, realistic) | n-1 |
| `ring` | Each account trusts the next, forming a ring | n |
| `mesh` | All pairs connected | n*(n-1)/2 |
| `random` | Random 30% of possible pairs | ~0.3 * n*(n-1)/2 |

## Backend Performance (1000 accounts, sequential)

| Algorithm | Backend | Library | Rate | Speedup |
|-----------|---------|---------|------|---------|
| ed25519 | native | PyNaCl (libsodium) | **22,568/sec** | 279x |
| ed25519 | fallback | xrpl-py (ecpy) | 81/sec | 1x |
| secp256k1 | native | coincurve (libsecp256k1) | ~15,000/sec* | ~250x |
| secp256k1 | native | fastecdsa (GMP) | **878/sec** | 14x |
| secp256k1 | fallback | xrpl-py (ecpy) | 61/sec | 1x |

*coincurve unavailable on Python 3.14, will auto-select when available

## Installing Native Backends

```bash
# For ed25519 (highly recommended - 279x speedup)
pip install pynacl

# For secp256k1 (recommended - 14-250x speedup)
pip install coincurve    # Best performance, requires Python <3.14
pip install fastecdsa    # Good fallback, works on Python 3.14
```

The script auto-detects available backends and uses the fastest one.

## Examples

```bash
# Check available backends
uv run scripts/bench_accounts.py --info

# Benchmark ed25519 (fastest with pynacl)
uv run scripts/bench_accounts.py -n 10000 --algo ed25519 --mode seq

# Benchmark with multiprocessing
uv run scripts/bench_accounts.py -n 10000 --algo secp256k1 --mode mp --workers 8

# Save results to JSON
uv run scripts/bench_accounts.py -n 1000 --output results.json

# Benchmark trustline generation (accounts + trustlines)
uv run scripts/bench_accounts.py -n 1000 --trustlines --mode mp

# Benchmark with different topologies
uv run scripts/bench_accounts.py -n 100 --trustlines --topology mesh --mode mp
uv run scripts/bench_accounts.py -n 1000 --trustlines --topology ring --mode mp

# Benchmark with multiple currencies
uv run scripts/bench_accounts.py -n 1000 --trustlines --currencies USD,EUR,JPY --mode mp
```

## Output Format

With `--output`, results are saved as JSON:

```json
{
  "meta": {
    "mode": "mp",
    "workers": 8,
    "account_count": 1000,
    "elapsed_accounts_sec": 0.044,
    "elapsed_seed_sec": 0.001,
    "algorithm": "ed25519",
    "backend": "pynacl",
    "account_rate": 22568.0,
    "trustline_count": 999,
    "elapsed_trustlines_sec": 0.15,
    "trustline_rate": 6660.0,
    "topology": "star",
    "currencies": ["USD"],
    "elapsed_total_sec": 0.195
  },
  "accounts": [
    {"address": "rXXX...", "seed": "abc123...", "index": "DEF456..."},
    ...
  ],
  "trustlines": [
    {"addr_a": "rXXX...", "addr_b": "rYYY...", "currency": "USD", "index": "ABC123..."},
    ...
  ]
}
```

The `trustlines` field is only present when `--trustlines` is used.

## Architecture

The script uses a modular architecture with swappable components:

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  CryptoBackend  │ --> │  AddressEncoder  │ --> │  account_root   │
│  (EC operations)│     │  (XRPL address)  │     │  _index()       │
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │                        │
        ▼                        ▼
  ┌───────────┐           ┌───────────┐
  │ PyNaCl    │           │ xrpl-py   │  (can be replaced
  │ coincurve │           │ or native │   with pure impl)
  │ fastecdsa │           └───────────┘
  │ fallback  │
  └───────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    Trustline Generation                         │
├─────────────────┬───────────────────┬───────────────────────────┤
│  Topology       │  Index Calc       │  Object Generation        │
│  (star/ring/    │  (SHA512-Half)    │  (RippleState +           │
│   mesh/random)  │                   │   2 DirectoryNodes)       │
└─────────────────┴───────────────────┴───────────────────────────┘
```

- **CryptoBackend**: Handles seed generation and keypair derivation
- **AddressEncoder**: Converts public key to XRPL classic address (r...)
- **account_root_index**: Computes AccountRoot ledger object index
- **Trustline Generation**: Self-contained implementation with:
  - **ripple_state_index**: SHA512-Half(0x0072 + low_acct + high_acct + currency)
  - **owner_dir_index**: SHA512-Half(0x004F + account_id)
  - **generate_trustline_objects**: Creates RippleState + 2 DirectoryNode dicts

## What is Benchmarked

**Account Generation**:
- Keypair derivation (EC point multiplication)
- Address encoding (SHA256 + RIPEMD160 + Base58Check)
- AccountRoot index calculation (SHA512-Half)

**Trustline Generation** (in-memory object creation):
- RippleState index calculation (SHA512-Half with account ordering)
- Owner directory index calculation (2 per trustline)
- Dict construction for RippleState and DirectoryNode objects

Note: This benchmarks CPU-bound cryptographic operations and object construction,
not network I/O or disk operations.
