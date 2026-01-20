# Data Model: XRPL Custom Ledger Environment Generator

**Feature**: 001-xrpl-ledger-generator
**Date**: 2025-12-10
**Source**: Derived from spec.md entities and research.md findings

## Overview

This document defines the data model for the XRPL Custom Ledger Environment Generator. The model represents the core entities involved in generating custom XRPL test environments, including configuration inputs, generated artifacts, and their relationships.

## Entity Diagram

```
Configuration
    ├──> LedgerConfig
    │      ├──> AccountConfig[]
    │      ├──> TrustlineConfig[]
    │      └──> ReserveConfig
    ├──> ValidatorConfig
    │      ├──> ValidatorIdentity[]
    │      └──> NetworkTopology
    └──> DeploymentConfig
           ├──> ContainerConfig[]
           └──> NetworkConfig

Generated Artifacts
    ├──> LedgerState (ledger.json)
    │      ├──> AccountRoot[]
    │      ├──> RippleState[]
    │      ├──> FeeSettings
    │      └──> Amendments
    ├──> ValidatorConfigs (rippled.cfg[])
    └──> DockerCompose (docker-compose.yml)
```

## Core Entities

### 1. Configuration Input Entities

#### AccountConfig
Represents configuration for generating XRPL accounts in the genesis ledger.

**Attributes**:
- `identifier`: string (optional) - Human-readable name (e.g., "alice", "bob")
- `balance`: string - Initial XRP balance in drops (e.g., "100000000000")
- `sequence`: integer - Starting sequence number (default: 1)
- `owner_count`: integer - Number of owned objects (default: 0)
- `flags`: integer - Account flags (default: 0)

**Validation Rules**:
- `balance` >= `account_reserve` + (`owner_count` × `owner_reserve`)
- `balance` must be numeric string representing drops
- `sequence` >= 1
- `identifier` must be unique if provided

**Relationships**:
- Belongs to `LedgerConfig`
- Generates `AccountRoot` ledger object
- May be referenced by `TrustlineConfig`

**Example**:
```python
AccountConfig(
    identifier="alice",
    balance="100000000000",  # 100k XRP
    sequence=1,
    owner_count=0,
    flags=0
)
```

#### TrustlineConfig
Represents configuration for generating trustlines (RippleState objects) between accounts.

**Attributes**:
- `currency`: string - 3-letter currency code or 40-char hex (e.g., "USD")
- `hi_account`: string - Higher account address or identifier
- `hi_limit`: string - High account's trust limit
- `lo_account`: string - Lower account address or identifier
- `lo_limit`: string - Low account's trust limit
- `balance`: string (optional) - Initial balance (default: "0")

**Validation Rules**:
- `currency` must be valid XRPL currency code
- `hi_account` and `lo_account` must exist in `AccountConfig`
- `hi_account` > `lo_account` (lexicographically by address)
- Limits must be positive numeric strings

**Relationships**:
- Belongs to `LedgerConfig`
- References two `AccountConfig` entities
- Generates `RippleState` ledger object

**Example**:
```python
TrustlineConfig(
    currency="USD",
    hi_account="alice",
    hi_limit="1000000",
    lo_account="bob",
    lo_limit="1000000",
    balance="0"
)
```

#### ReserveConfig
Represents the reserve requirements and fee settings for the ledger.

**Attributes**:
- `reference_fee`: integer - Base transaction fee in drops (default: 10)
- `account_reserve`: integer - Base account reserve in drops (default: 2000000)
- `owner_reserve`: integer - Per-object reserve in drops (default: 200000)

**Validation Rules**:
- `reference_fee` >= 10
- `account_reserve` >= 1000000 (1 XRP minimum recommended)
- `owner_reserve` >= 100000 (0.1 XRP minimum recommended)
- All values must be positive integers

**Relationships**:
- Belongs to `LedgerConfig`
- Generates `FeeSettings` ledger object
- Referenced in validator `[voting]` configuration

**Example**:
```python
ReserveConfig(
    reference_fee=10,
    account_reserve=2000000,     # 2 XRP
    owner_reserve=200000         # 0.2 XRP
)
```

#### LedgerConfig
Aggregates all ledger state configuration.

**Attributes**:
- `accounts`: list[AccountConfig] - Account configurations
- `trustlines`: list[TrustlineConfig] - Trustline configurations
- `reserves`: ReserveConfig - Reserve and fee settings
- `amendments`: list[string] - Enabled amendment hashes
- `total_coins`: string - Total XRP supply (default: "100000000000000000")

**Validation Rules**:
- At least one account must be defined
- Sum of all account balances must equal `total_coins`
- All trustline accounts must exist in `accounts`
- All account balances must meet reserve requirements

**Relationships**:
- Contains multiple `AccountConfig`
- Contains multiple `TrustlineConfig`
- Contains one `ReserveConfig`
- Generates complete `LedgerState`

#### ValidatorIdentity
Represents a single validator's cryptographic identity.

**Attributes**:
- `name`: string - Validator identifier (e.g., "val0", "val1")
- `public_key`: string - Validator public key (n9... format)
- `validation_seed`: string - Validation seed (s... format)
- `algorithm`: string - Cryptographic algorithm (default: "secp256k1")

**Validation Rules**:
- `public_key` must start with "n9"
- `validation_seed` must start with "s"
- `name` must be unique within validator set
- `algorithm` must be valid XRPL algorithm

**Relationships**:
- Belongs to `ValidatorConfig`
- Referenced in UNL (Unique Node List)
- Embedded in validator's rippled.cfg

**Example**:
```python
ValidatorIdentity(
    name="val0",
    public_key="n9M8j6NSHEu1b8ieDgiBgwLev8bFVqYWhJvzEoLvKdgSvJmbLN3F",
    validation_seed="ssFMztqLbZTgLti9n9XTyMqLBAkKy",
    algorithm="secp256k1"
)
```

#### NetworkTopology
Defines the network connectivity between validators.

**Attributes**:
- `validator_count`: integer - Number of validators
- `peer_port`: integer - Peer protocol port (default: 51235)
- `full_mesh`: boolean - Whether all validators connect to each other (default: true)

**Validation Rules**:
- `validator_count` >= 4 (minimum for Byzantine fault tolerance)
- `validator_count` <= 10 (recommended maximum for test networks)
- `peer_port` must be valid port number (1-65535)

**Relationships**:
- Belongs to `ValidatorConfig`
- Determines `[ips_fixed]` configuration in rippled.cfg

#### ValidatorConfig
Aggregates validator configuration.

**Attributes**:
- `validators`: list[ValidatorIdentity] - Validator identities
- `topology`: NetworkTopology - Network topology
- `reserves`: ReserveConfig - Must match LedgerConfig reserves

**Validation Rules**:
- `validators` length must equal `topology.validator_count`
- `reserves` must match `LedgerConfig.reserves`
- All validator names must be unique

**Relationships**:
- Contains multiple `ValidatorIdentity`
- Contains one `NetworkTopology`
- References `ReserveConfig` from `LedgerConfig`
- Generates multiple rippled.cfg files

#### ContainerConfig
Represents a single container's Docker configuration.

**Attributes**:
- `name`: string - Container/service name (e.g., "val0", "rippled")
- `hostname`: string - Container hostname (default: same as name)
- `image`: string - Docker image (default: "rippleci/rippled:develop")
- `command`: list[string] - Container command (e.g., ["--ledgerfile", "/ledger.json"])
- `ports`: dict[string, string] - Port mappings (e.g., {"5005": "5006"})
- `volumes`: list[string] - Volume mounts
- `depends_on`: list[string] - Dependency services
- `is_validator`: boolean - Whether container runs a validator

**Validation Rules**:
- `name` must be unique within deployment
- `hostname` must be valid DNS hostname
- Port mappings must not conflict
- Volume paths must be valid

**Relationships**:
- Belongs to `DeploymentConfig`
- May depend on other `ContainerConfig` entities

**Example**:
```python
ContainerConfig(
    name="val0",
    hostname="val0",
    image="rippleci/rippled:develop",
    command=["--ledgerfile", "/ledger.json"],
    ports={"5005": "5006", "6006": "6007"},
    volumes=["./volumes/val0:/etc/opt/ripple", "./ledger.json:/ledger.json"],
    depends_on=[],
    is_validator=True
)
```

#### NetworkConfig
Represents Docker network configuration.

**Attributes**:
- `name`: string - Network name (default: "xrpl_net")
- `driver`: string - Network driver (default: "bridge")
- `isolated`: boolean - Whether network is isolated (default: true)

**Validation Rules**:
- `name` must be valid Docker network name
- `driver` must be valid Docker network driver

**Relationships**:
- Belongs to `DeploymentConfig`
- Referenced by all `ContainerConfig` entities

#### DeploymentConfig
Aggregates Docker deployment configuration.

**Attributes**:
- `containers`: list[ContainerConfig] - Container configurations
- `network`: NetworkConfig - Network configuration

**Validation Rules**:
- At least one validator container must exist
- Container names must be unique
- Dependency graph must be acyclic

**Relationships**:
- Contains multiple `ContainerConfig`
- Contains one `NetworkConfig`
- Generates docker-compose.yml

### 2. Generated Artifact Entities

#### AccountRoot
Represents an XRPL account in the ledger.

**Attributes**:
- `LedgerEntryType`: "AccountRoot" (constant)
- `Account`: string - XRPL address (r... format)
- `Balance`: string - Balance in drops
- `Sequence`: integer - Next transaction sequence
- `OwnerCount`: integer - Number of owned objects
- `Flags`: integer - Account flags
- `PreviousTxnID`: string - Previous transaction hash (zeros for genesis)
- `PreviousTxnLgrSeq`: integer - Previous transaction ledger seq (0 for genesis)
- `index`: string - Ledger object index (SHA-512-Half)

**Index Calculation**:
```python
def account_root_index(address: str) -> str:
    account_id = base58.b58decode_check(address)[1:]
    preimage = b"\x00\x61" + account_id  # 0x0061 = ACCOUNT namespace
    return hashlib.sha512(preimage).digest()[:32].hex().upper()
```

**Source**: Generated from `AccountConfig`

#### RippleState
Represents a trustline between two accounts.

**Attributes**:
- `LedgerEntryType`: "RippleState" (constant)
- `Balance`: object - Current balance with currency/issuer
- `HighLimit`: object - High account's limit with currency/issuer
- `LowLimit`: object - Low account's limit with currency/issuer
- `HighNode`: string - Directory node for high account (usually "0")
- `LowNode`: string - Directory node for low account (usually "0")
- `Flags`: integer - Trustline flags
- `PreviousTxnID`: string - Previous transaction hash
- `PreviousTxnLgrSeq`: integer - Previous transaction ledger seq
- `index`: string - Ledger object index (SHA-512-Half)

**Index Calculation**:
```python
def ripple_state_index(lo_address: str, hi_address: str, currency: str) -> str:
    # Implementation in src/generate_ledger/indices.py
    lo_account_id = base58.b58decode_check(lo_address)[1:]
    hi_account_id = base58.b58decode_check(hi_address)[1:]
    currency_code = encode_currency(currency)  # 20 bytes
    preimage = b"\x00\x72" + lo_account_id + hi_account_id + currency_code
    return hashlib.sha512(preimage).digest()[:32].hex().upper()
```

**Source**: Generated from `TrustlineConfig`

#### FeeSettings
Represents ledger fee and reserve settings.

**Attributes**:
- `LedgerEntryType`: "FeeSettings" (constant)
- `BaseFeeDrops`: integer - Base transaction fee
- `ReserveBaseDrops`: integer - Account reserve
- `ReserveIncrementDrops`: integer - Per-object reserve
- `Flags`: integer - Always 0
- `index`: "4BC50C9B0D8515D3EAAE1E74B29A95804346C491EE1A95BF25E4AAB854A6A651" (fixed constant)

**Source**: Generated from `ReserveConfig`

#### Amendments
Represents enabled amendments in the ledger.

**Attributes**:
- `LedgerEntryType`: "Amendments" (constant)
- `Amendments`: list[string] - Array of enabled amendment hashes (64-char hex)
- `Flags`: integer - Always 0
- `index`: "7DB0788C020F02780A673DC74757F23823FA3014C1866E72CC4CD8B226CD6EF4" (fixed constant)

**Source**: Generated from `LedgerConfig.amendments`

#### LedgerState
Represents the complete genesis ledger.

**Attributes**:
- `ledger`: object containing:
  - `accepted`: boolean - Always true
  - `accountState`: array - All ledger objects (AccountRoot, RippleState, FeeSettings, Amendments)
  - `close_time_resolution`: integer - Always 10
  - `totalCoins`: string - Total XRP supply
  - `total_coins`: string - Duplicate of totalCoins

**Source**: Aggregates all ledger objects

**Output**: ledger.json file

## Data Relationships

```
LedgerConfig
    accounts (1:N) ──> AccountConfig ──generates──> AccountRoot
    trustlines (1:N) ──> TrustlineConfig ──generates──> RippleState
    reserves (1:1) ──> ReserveConfig ──generates──> FeeSettings
    amendments (1:N) ──> AmendmentHash ──generates──> Amendments

ValidatorConfig
    validators (1:N) ──> ValidatorIdentity ──embeds_in──> rippled.cfg
    topology (1:1) ──> NetworkTopology ──determines──> [ips_fixed] section
    reserves (reference) ──> ReserveConfig ──embeds_in──> [voting] section

DeploymentConfig
    containers (1:N) ──> ContainerConfig ──defines──> docker-compose service
    network (1:1) ──> NetworkConfig ──defines──> docker-compose network
```

## Validation Dependencies

**Cross-Entity Validations**:

1. **Balance-Reserve Consistency**:
   - For each `AccountConfig`: `balance` >= `reserves.account_reserve` + (`owner_count` × `reserves.owner_reserve`)

2. **Total Supply Consistency**:
   - Sum of all `AccountConfig.balance` must equal `LedgerConfig.total_coins`

3. **Trustline Account Existence**:
   - `TrustlineConfig.hi_account` must exist in `LedgerConfig.accounts`
   - `TrustlineConfig.lo_account` must exist in `LedgerConfig.accounts`

4. **Validator-Reserve Consistency**:
   - `ValidatorConfig.reserves` must match `LedgerConfig.reserves`

5. **Container Dependency Ordering**:
   - Bootstrap validator (val0) must have no dependencies
   - Other validators must depend on bootstrap validator
   - Non-validator nodes may depend on any validator

## State Transitions

```
Input Configuration Phase:
    User Input ──> LedgerConfig + ValidatorConfig + DeploymentConfig

Generation Phase:
    LedgerConfig ──generate──> LedgerState (ledger.json)
    ValidatorConfig ──generate──> rippled.cfg files
    DeploymentConfig ──generate──> docker-compose.yml

Deployment Phase:
    ledger.json + rippled.cfg[] + docker-compose.yml ──deploy──> Running Network
```

## Implementation Notes

### Existing Implementations

**Account Generation**: `src/generate_ledger/accounts.py`
```python
@dataclass
class Account:
    address: str
    seed: str

class AccountConfig(BaseSettings):
    num_accounts: PositiveInt = 2
    algo: CryptoAlgorithm = CryptoAlgorithm.SECP256K1
    balance: str = str(100_000_000000)
```

**Trustline Generation**: `src/generate_ledger/trustlines.py`
```python
@dataclass
class Trustline:
    currency: str
    hi_address: str
    hi_amount: PositiveInt
    lo_address: str
    lo_amount: PositiveInt
```

**Validator Config**: `src/generate_ledger/rippled_cfg.py`
```python
class RippledConfigSpec(BaseSettings):
    num_validators: int = 5
    validator_name: str = "val"
    peer_port: int = 51235
    reference_fee: int = 10
    account_reserve: int = int(0.2 * 1e6)
    owner_reserve: int = int(1.0 * 1e6)
```

**Docker Compose**: `src/generate_ledger/compose.py`
```python
class ComposeConfig(BaseSettings):
    num_validators: int = 5
    validator_name: str = "val"
    validator_image: str = "rippleci/rippled"
    validator_image_tag: str = "develop"
    network_name: str = "xrpl_net"
```

### Extension Points

**For MPT Support** (Phase 2):
```python
class MPTConfig:
    issuer_account: str
    asset_scale: int
    maximum_amount: str
    transfer_fee: int
    flags: int
    metadata: str
```

**For AMM Support** (Phase 2):
```python
class AMMConfig:
    creator_account: str
    asset1: str
    asset2: str
    amount1: str
    amount2: str
    trading_fee: int
```

**For Lending/Vault Support** (Phase 3):
```python
class VaultConfig:
    owner_account: str
    asset_type: str
    assets_maximum: str
    withdrawal_policy: int
    metadata: str
```

## Summary

This data model provides a structured representation of:
- **Input Configuration**: What users specify to generate test environments
- **Generated Artifacts**: What files/objects are produced
- **Validation Rules**: How to ensure consistency
- **Relationships**: How entities connect to each other

The model supports the existing codebase patterns while providing extension points for future enhancements (MPT, AMM, Lending/Vault).
