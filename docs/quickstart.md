# Quick Start

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) -- Python package manager
- [Docker](https://docs.docker.com/engine/install/) -- Container runtime
- [Docker Compose](https://docs.docker.com/compose/install/) -- Multi-container orchestration

## Start a Test Network

Clone the repo, install dependencies, and generate a complete test environment:

```bash
git clone https://github.com/legleux/generate_ledger.git
cd generate_ledger
uv sync
uv run gen
```

This creates a `testnet/` directory with everything needed to boot a private XRPL network:

- `ledger.json` -- Genesis ledger with pre-funded accounts and enabled amendments
- `accounts.json` -- Account credentials (addresses, seeds, keys)
- `volumes/val0/xrpld.cfg` through `valN/xrpld.cfg` -- Validator configurations with UNL
- `docker-compose.yml` -- Ready-to-run Docker deployment

Start the network:

```bash
cd testnet
docker compose up
```

In under a minute, verify a validator is proposing:

```bash
curl -s localhost:5006 -d '{"method": "server_info"}' | jq .result.info.server_state
# "proposing"
```

You can also observe the network live in the XRPL explorer at
[https://custom.xrpl.org/localhost:6007](https://custom.xrpl.org/localhost:6007).

The default ports for val0 are **5006** (RPC) and **6007** (WebSocket). These shift based
on the number of validators and hubs configured.

### Crypto backends

For faster account generation, install the optional crypto backends:

```bash
uv sync --group fast   # + PyNaCl, coincurve (~25k accounts/sec)
uv sync --group gpu    # + CuPy, CUDA toolkit (~280k accounts/sec, requires NVIDIA GPU)
uv run gen --gpu       # use GPU for account generation
```

## Customize Your Network

### Generate Just a Ledger

```bash
uv run gen ledger --accounts 10 --output-dir ./my-ledger
```

### Add Trustlines and AMM Pools

```bash
uv run gen ledger --accounts 50 --output-dir ./out \
  -t "0:1:USD:1000000000" \
  -a "XRP:USD:0:1000000000000:1000000:500:0"
```

### Customize Account and Validator Counts

```bash
uv run gen --accounts 50 --validators 5 --output-dir ./my-testnet
```

### Add Gateway Topology

```bash
uv run gen ledger --accounts 100 --output-dir ./out \
  --gateways 4 --assets-per-gateway 3 --gateway-coverage 0.8
```

## What Next

- See the [CLI Reference](cli.md) for all available options
- Use `generate_ledger` [as a library](library.md) in your Python code
- Learn about [amendment profiles](amendments.md) to control which amendments are enabled
