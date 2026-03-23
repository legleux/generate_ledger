# Library API

`generate_ledger` can be used as a Python library to programmatically create XRPL genesis ledgers without invoking the CLI.

## Install

```bash
pip install generate-ledger
```

## Quick Start

```python
from generate_ledger.ledger import LedgerConfig, gen_ledger_state

# Generate a ledger dict in memory (no file I/O)
ledger = gen_ledger_state(
    LedgerConfig(amendment_profile="release"),
    write_accounts=False,
)

# ledger is a dict ready for json.dump() or direct use
print(len(ledger["ledger"]["accountState"]))
```

## Configuration

All options are set via `LedgerConfig`. Every field has a sensible default.

```python
from generate_ledger.accounts import AccountConfig
from generate_ledger.gateways import GatewayConfig
from generate_ledger.ledger import AMMPoolConfig, ExplicitTrustline, FeeConfig, LedgerConfig
from generate_ledger.trustlines import TrustlineConfig

config = LedgerConfig(
    # Accounts
    account_cfg=AccountConfig(
        num_accounts=100,          # total accounts (including gateways)
        balance="100000000000",    # per-account balance in drops (100k XRP)
        algo="ed25519",            # "ed25519" (fast) or "secp256k1"
    ),

    # Fees
    fee_cfg=FeeConfig(
        base_fee_drops=10,
        reserve_base_drops=200000,
        reserve_increment_drops=50000,
    ),

    # Random trustlines
    trustlines=TrustlineConfig(
        num_trustlines=20,
        currencies=["USD", "EUR"],
        default_limit="100000000000",
    ),

    # Explicit trustlines (by account index or address)
    explicit_trustlines=[
        ExplicitTrustline(account1=0, account2=1, currency="USD", limit=1_000_000_000),
    ],

    # Gateway topology
    gateway_cfg=GatewayConfig(
        num_gateways=4,
        assets_per_gateway=3,
        currencies=["USD", "EUR", "GBP", "JPY"],
        coverage=0.8,              # 80% of accounts get trustlines
        connectivity=0.5,          # each account connects to 50% of gateways
    ),

    # AMM pools
    amm_pools=[
        AMMPoolConfig(
            asset1_currency="XRP",
            asset1_issuer=None,     # None for XRP
            asset1_amount=1_000_000_000_000,
            asset2_currency="USD",
            asset2_issuer=0,        # account index 0
            asset2_amount=1_000_000,
            trading_fee=500,
        ),
    ],

    # Amendments
    amendment_profile="release",   # "release", "develop", or "custom"
    # amendment_profile_source="/path/to/features.macro",  # for develop/custom
    # enable_amendments=["SomeFeature"],
    # disable_amendments=["Clawback"],

    # Output directory (only used if write_accounts=True or write_ledger_file)
    base_dir="./my-testnet",
)
```

## API Reference

### `gen_ledger_state(config, *, write_accounts=True) -> dict`

Generate a complete ledger as a Python dict.

- **`config`**: `LedgerConfig` instance (or `None` for defaults)
- **`write_accounts`**: Set to `False` to skip writing `accounts.json` to disk. Use this when you only need the ledger data in memory.

Returns a dict with the structure rippled expects for genesis ledger loading.

### `write_ledger_file(output_file, config, *, quiet=False) -> Path`

Generate a ledger and write it to disk as JSON.

- **`output_file`**: Output path (default: `config.base_dir/ledger.json`)
- **`config`**: `LedgerConfig` instance (or `None` for defaults)
- **`quiet`**: Set to `True` to suppress console output

Returns the resolved path to the written file. Also writes `accounts.json` alongside it.

### `generate_accounts(config) -> list[Account]`

Generate XRPL accounts without building a full ledger.

```python
from generate_ledger.accounts import AccountConfig, generate_accounts

accounts = generate_accounts(AccountConfig(num_accounts=10, algo="ed25519"))
for acct in accounts:
    print(acct.address, acct.seed)
```

### `generate_amm_objects(spec) -> list[dict]`

Generate AMM ledger objects from an `AMMSpec`.

```python
from generate_ledger.amm import AMMSpec, Asset, generate_amm_objects

spec = AMMSpec(
    asset1=Asset(currency="XRP", issuer=None, amount=1_000_000_000),
    asset2=Asset(currency="USD", issuer="rISSUER...", amount=1_000),
    trading_fee=500,
    creator=account,  # an Account object
)
objects = generate_amm_objects(spec)
```

## Typical Integration Pattern

```python
import json
from generate_ledger.accounts import AccountConfig
from generate_ledger.ledger import LedgerConfig, gen_ledger_state

def make_test_ledger(num_accounts: int = 50) -> dict:
    """Create a genesis ledger for integration tests."""
    config = LedgerConfig(
        account_cfg=AccountConfig(num_accounts=num_accounts, algo="ed25519"),
        amendment_profile="release",
    )
    return gen_ledger_state(config, write_accounts=False)

# Use directly
ledger = make_test_ledger()

# Or write to a file yourself
with open("ledger.json", "w") as f:
    json.dump(ledger, f)
```

## Environment Variables

`LedgerConfig` is a pydantic-settings `BaseSettings` class. All fields can be set via `GL_`-prefixed environment variables:

```bash
export GL_BASE_DIR=/tmp/testnet
export GL_ACCOUNT__NUM_ACCOUNTS=100
export GL_ACCOUNT__ALGO=ed25519
```

Or via a `.env` file in the working directory. Nested fields use `__` as a delimiter.
