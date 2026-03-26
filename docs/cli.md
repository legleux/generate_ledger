# CLI Reference

The CLI entry point is `gen`. Running `gen` with no subcommand executes the full pipeline (ledger + xrpld configs + docker-compose). Two subcommands are available for running individual steps: `ledger` and `xrpld`.

## gen ledger

Generate a genesis ledger with pre-funded accounts, trustlines, AMM pools, and amendments.

```bash
gen ledger --accounts 100 --output-dir ./output
```

### Account Options

| Option                | Default        | Description                                        |
| --------------------- | -------------- | -------------------------------------------------- |
| `--accounts`          | 10             | Number of regular (non-gateway) accounts           |
| `--algo`              | `ed25519`      | Key algorithm: `ed25519` or `secp256k1`            |
| `--balance`           | `100000000000` | Per-account balance in drops (100k XRP)            |
| `--output-dir` / `-o` | `./testnet`    | Output directory for ledger.json and accounts.json |

### Trustline Options

```bash
# Explicit trustline: account 0 trusts account 1 for USD, limit 1B
gen ledger --accounts 10 -o ./out -t "0:1:USD:1000000000"

# Random trustlines (star topology from account 0)
gen ledger --accounts 100 -o ./out --num-trustlines 20

# Multiple currencies
gen ledger --accounts 50 -o ./out --currencies USD,EUR,JPY --num-trustlines 10
```

| Option               | Default | Description                                                                  |
| -------------------- | ------- | ---------------------------------------------------------------------------- |
| `-t` / `--trustline` | --      | Explicit trustline in `account1:account2:currency:limit` format (repeatable) |
| `--num-trustlines`   | 0       | Number of random trustlines to generate                                      |
| `--currencies`       | `USD`   | Comma-separated currency list for random trustlines                          |

### AMM Pool Options

```bash
# XRP/USD pool: issuer=account 0, XRP deposit=1T drops, USD deposit=1M, LP tokens=500, fee=0
gen ledger --accounts 10 -o ./out \
  -t "0:1:USD:1000000000" \
  -a "XRP:USD:0:1000000000000:1000000:500:0"
```

| Option         | Default | Description                                                                          |
| -------------- | ------- | ------------------------------------------------------------------------------------ |
| `-a` / `--amm` | --      | AMM pool in `asset1:asset2:issuer:amount1:amount2:lp_tokens:fee` format (repeatable) |

### Gateway Options

Gateway accounts issue assets and create a realistic trustline topology across the network.

```bash
gen ledger --accounts 100 -o ./out \
  --gateways 4 --assets-per-gateway 3 --gateway-coverage 0.8
```

| Option                   | Default                                   | Description                                                        |
| ------------------------ | ----------------------------------------- | ------------------------------------------------------------------ |
| `--gateways`             | 0                                         | Number of gateway accounts (first N accounts become gateways)      |
| `--assets-per-gateway`   | 4                                         | Unique assets each gateway issues                                  |
| `--gateway-currencies`   | `USD,EUR,GBP,JPY,BTC,ETH,CNY,MXN,CAD,AUD` | Currency pool (distributed round-robin)                            |
| `--gateway-coverage`     | 0.5                                       | Fraction of non-gateway accounts that receive trustlines (0.0-1.0) |
| `--gateway-connectivity` | 0.5                                       | Fraction of gateways each account connects to (0.0-1.0)            |
| `--gateway-seed`         | --                                        | RNG seed for reproducible topology                                 |

### Fee Options

```bash
gen ledger --accounts 10 --base-fee 10 --reserve-base 200000 --reserve-inc 50000
```

| Option           | Default | Description                                |
| ---------------- | ------- | ------------------------------------------ |
| `--base-fee`     | 121     | Base transaction fee (drops)               |
| `--reserve-base` | 2000000 | Account reserve base (drops)               |
| `--reserve-inc`  | 666     | Owner reserve increment per object (drops) |

### Amendment Options

```bash
# Curated mainnet amendments (default)
gen ledger --accounts 10 --amendment-profile release

# Parse from a local xrpld features.macro
gen ledger --accounts 10 --amendment-profile develop \
  --amendment-source /path/to/xrpld/include/xrpl/protocol/detail/features.macro

# Per-amendment overrides
gen ledger --accounts 10 --enable-amendment SomeFeature --disable-amendment Clawback
```

| Option                | Default   | Description                                          |
| --------------------- | --------- | ---------------------------------------------------- |
| `--amendment-profile` | `release` | Amendment profile: `release`, `develop`, or `custom` |
| `--amendment-source`  | --        | Path to `features.macro` or custom JSON file         |
| `--enable-amendment`  | --        | Force-enable a specific amendment (repeatable)       |
| `--disable-amendment` | --        | Force-disable a specific amendment (repeatable)      |

### MPT Options (develop branch)

```bash
gen ledger --accounts 10 -o ./out --mpt "0:1"
```

| Option  | Default | Description                                                                              |
| ------- | ------- | ---------------------------------------------------------------------------------------- |
| `--mpt` | --      | MPT issuance in `issuer:sequence[:max_amount[:flags[:asset_scale]]]` format (repeatable) |

---

## gen auto

Generate a complete test environment: ledger + validator configs + docker-compose.

```bash
gen auto --accounts 100 --validators 5 --output-dir ./testnet
```

`gen auto` supports **all** `gen ledger` options (accounts, trustlines, AMM, gateways, amendments, fees), plus:

| Option                      | Default | Description                                         |
| --------------------------- | ------- | --------------------------------------------------- |
| `--validators` / `-v`       | 5       | Number of validator nodes                           |
| `--peer-port`               | 51235   | Port used in `[ips_fixed]` entries                  |
| `--amendment-majority-time` | --      | Override amendment majority time (e.g. `2 minutes`) |

### Example

```bash
gen auto --accounts 200 -v 5 -o ./testnet \
  --gateways 4 --assets-per-gateway 3 --gateway-coverage 0.8 \
  --base-fee 10 --reserve-base 200000 --reserve-inc 50000
```

---

## gen xrpld

Generate validator configurations (xrpld.cfg files with UNL and voting stanzas).

```bash
gen xrpld -v 5 -b ./testnet/volumes
```

| Option                      | Default           | Description                                 |
| --------------------------- | ----------------- | ------------------------------------------- |
| `--validators` / `-v`       | 5                 | Number of validator nodes                   |
| `--base-dir` / `-b`         | `testnet/volumes` | Output directory for node subdirs           |
| `--template-path` / `-t`    | built-in          | Path to base `xrpld.cfg` template           |
| `--peer-port`               | 51235             | Port for `[ips_fixed]` entries              |
| `--reference-fee`           | 10                | Voting: reference fee (drops)               |
| `--account-reserve`         | 200000            | Voting: account reserve (drops)             |
| `--owner-reserve`           | 1000000           | Voting: owner reserve (drops)               |
| `--keygen`                  | `xrpl`            | Key generation backend (`xrpl` or `docker`) |
| `--amendment-majority-time` | --                | Override amendment majority time            |

---

## gen compose write

Generate a `docker-compose.yml` for the validator cluster.

```bash
gen compose write -v 5 -o ./testnet/docker-compose.yml
```

| Option                 | Default | Description                 |
| ---------------------- | ------- | --------------------------- |
| `--validators` / `-v`  | --      | Number of validator nodes   |
| `--output-file` / `-o` | --      | Output file path            |
| `--validator-image`    | --      | Docker image for validators |
| `--validator-version`  | --      | Image version tag           |
| `--hubs`               | --      | Number of hub nodes         |
