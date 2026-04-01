# Amendment System

`generate_ledger` supports three amendment profiles that control which XRPL amendments are enabled in the genesis ledger. On the live XRPL network, amendments are protocol changes that activate only after reaching 80% validator consensus. In a genesis ledger, you choose which amendments to enable upfront — this determines the protocol rules your test network starts with.

## Profiles

### release (default)

The `release` profile fetches the list of amendments currently enabled on the XRPL mainnet by querying a mainnet RPC node. If the network request fails, it falls back to a bundled JSON snapshot (`amendments_mainnet.json`).

```bash
gen ledger --accounts 10 --amendment-profile release
```

This gives you the same amendment set as the production XRPL network -- useful for testing behavior that matches mainnet.

### develop

The `develop` profile fetches `features.macro` from the rippled repository's `develop` branch on GitHub and parses it to extract all supported amendments. It enables all amendments that have `Supported::yes` status.

```bash
gen ledger --accounts 10 --amendment-profile develop
```

You can point it at a local `features.macro` file instead of fetching from GitHub:

```bash
gen ledger --accounts 10 --amendment-profile develop \
  --amendment-source /path/to/rippled/include/xrpl/protocol/detail/features.macro
```

This is useful when working with a local rippled checkout, especially on a feature branch that introduces new amendments.

!!! note "Supported vs. Enabled"
`features.macro` defines what amendments a rippled build **supports** -- not what is enabled on a live network. Amendments are enabled on mainnet only after reaching 80% validator consensus, which can lag weeks or months behind a release. The `develop` profile enables all supported amendments, matching the behavior of a freshly started test network where all supported amendments activate immediately.

### custom

The `custom` profile loads amendments from a user-provided JSON file.

```bash
gen ledger --accounts 10 --amendment-profile custom \
  --amendment-source /path/to/my-amendments.json
```

The JSON file should be a dict keyed by amendment hash:

```json
{
  "8CC0774A3BF66D1D22E76BBDA8E8A232E6B6313834301B3B23E8601196AE6455": {
    "name": "AMM",
    "enabled": true,
    "supported": true
  }
}
```

## Per-Amendment Overrides

Regardless of the selected profile, you can force-enable or force-disable individual amendments:

```bash
gen ledger --accounts 10 \
  --enable-amendment SomeFeature \
  --disable-amendment Clawback
```

Both flags are repeatable:

```bash
gen ledger --accounts 10 \
  --enable-amendment FeatureA \
  --enable-amendment FeatureB \
  --disable-amendment ObsoleteFeature
```

Overrides are applied after the profile is loaded, so `--disable-amendment` can remove an amendment that the profile would otherwise include, and `--enable-amendment` can add one that the profile does not include.

## Environment Variable: GL_FEATURES_MACRO

When using the `develop` profile, you can set the `GL_FEATURES_MACRO` environment variable to point at a local `features.macro` file instead of using the `--amendment-source` CLI flag:

```bash
export GL_FEATURES_MACRO=/home/user/rippled/include/xrpl/protocol/detail/features.macro
gen ledger --accounts 10 --amendment-profile develop
```

## How features.macro Parsing Works

The parser handles three macro types from rippled's `features.macro`:

- **`XRPL_FEATURE(Name, Supported, VoteBehavior)`** -- Standard amendment
- **`XRPL_FIX(Name, Supported, VoteBehavior)`** -- Fix amendment (prefixed with "fix" in the amendment name)
- **`XRPL_RETIRE_FEATURE(Name)` / `XRPL_RETIRE_FIX(Name)`** -- Retired amendments (excluded from the enabled set)

The parser extracts the amendment name, computes its SHA-512 Half hash (matching rippled's implementation), and includes it if the amendment is supported and not retired.

## How Amendment Hashes Work

Each amendment is identified by a 64-character hex string computed as `SHA512Half(amendment_name)`. This matches rippled's `Feature.cpp` implementation. The hash is deterministic -- given the same amendment name, the hash is always the same.

```python
from generate_ledger.amendments import amendment_hash

h = amendment_hash("AMM")
# Returns the SHA512Half of "AMM" as uppercase hex
```

## Library Usage

When using `generate_ledger` as a library, amendment configuration is part of `LedgerConfig`:

```python
from generate_ledger.ledger import LedgerConfig, gen_ledger_state

config = LedgerConfig(
    amendment_profile="release",
    # amendment_profile_source="/path/to/features.macro",
    # enable_amendments=["SomeFeature"],
    # disable_amendments=["Clawback"],
)

ledger = gen_ledger_state(config, write_accounts=False)
```
