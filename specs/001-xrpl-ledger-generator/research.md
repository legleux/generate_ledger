# Research: XRPL Custom Ledger Environment Generator

**Date**: 2025-12-10
**Phase**: Phase 0 - Research & Discovery

## Executive Summary

This document consolidates research findings for all technical clarifications identified in the implementation plan. The research addresses six key areas: XRPL genesis ledger format, MPT creation, AMM initialization, lending protocol primitives, validator configuration, and Docker networking.

### Key Findings

1. **Genesis Ledger Format**: Well-defined structure for pre-generating AccountRoot, FeeSettings, Amendments, and RippleState objects
2. **MPT Objects**: Theoretically pre-generable but NOT RECOMMENDED - use post-genesis transactions
3. **AMM Pools**: CANNOT be pre-generated - MUST be created via transactions after network start
4. **Lending Protocol**: No official lending protocol exists; use Vault feature (experimental) or existing primitives (Escrow, Trustlines)
5. **Validator Configuration**: Comprehensive patterns exist for key generation, config files, and UNL setup
6. **Docker Networking**: Custom bridge networks with DNS-based peer discovery is optimal

---

## 1. XRPL Genesis Ledger Format

**Decision**: Use JSON format with AccountRoot, FeeSettings, Amendments, and RippleState objects

**Rationale**: The existing codebase successfully generates genesis ledgers with these object types. The format is validated and working in production test networks.

### JSON Structure

```json
{
  "ledger": {
    "accepted": true,
    "accountState": [ /* array of ledger objects */ ],
    "close_time_resolution": 10,
    "totalCoins": "100000000000000000",
    "total_coins": "100000000000000000"
  }
}
```

### Required Ledger Objects

#### 1. AccountRoot (One or more)
```json
{
  "Account": "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh",
  "Balance": "99990000000000000",
  "Flags": 0,
  "LedgerEntryType": "AccountRoot",
  "OwnerCount": 0,
  "PreviousTxnID": "0000000000000000000000000000000000000000000000000000000000000000",
  "PreviousTxnLgrSeq": 0,
  "Sequence": 1,
  "index": "2B6AC232AA4C4BE41BF49D2459FA4A0347E1B543A4C92FCEE0821C0201E2E9A8"
}
```

**Index Calculation**:
```python
def account_root_index(address: str) -> str:
    account_id = base58.b58decode_check(address, alphabet=base58.XRP_ALPHABET)[1:]
    preimage = b"\x00\x61" + account_id  # 0x0061 = ACCOUNT namespace
    return hashlib.sha512(preimage).digest()[:32].hex().upper()
```

#### 2. FeeSettings (Exactly one required)
```json
{
  "LedgerEntryType": "FeeSettings",
  "BaseFeeDrops": 10,
  "Flags": 0,
  "ReserveBaseDrops": 2000000,
  "ReserveIncrementDrops": 200000,
  "index": "4BC50C9B0D8515D3EAAE1E74B29A95804346C491EE1A95BF25E4AAB854A6A651"
}
```

**CRITICAL**: The index is a fixed constant.

#### 3. Amendments (Exactly one required)
```json
{
  "Amendments": [
    "00C1FC4A53E60AB02C864641002B3172F38677E29C26C5406685179B37E1EDAC",
    "03BDC0099C4E14163ADA272C1B6F6FABB448CC3E51F522F978041E4B57D9158C",
    ...
  ],
  "Flags": 0,
  "LedgerEntryType": "Amendments",
  "index": "7DB0788C020F02780A673DC74757F23823FA3014C1866E72CC4CD8B226CD6EF4"
}
```

**CRITICAL**: The index is a fixed constant. Include 71+ enabled amendments for full XRPL functionality.

#### 4. RippleState (Trustlines) - Optional but supported
```json
{
  "Balance": {"currency": "USD", "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji", "value": "0"},
  "Flags": 131072,
  "HighLimit": {"currency": "USD", "issuer": "rHighAddress", "value": "1000000"},
  "HighNode": "0",
  "LedgerEntryType": "RippleState",
  "LowLimit": {"currency": "USD", "issuer": "rLowAddress", "value": "1000000"},
  "LowNode": "0",
  "PreviousTxnID": "72DC4832A16946423E1B29A971A98420D803FF24BA7309DC84F362AFBF84296F",
  "PreviousTxnLgrSeq": 404995,
  "index": "CALCULATED_RIPPLE_STATE_INDEX"
}
```

### Validation Rules

1. **Balance Constraints**: Every account's Balance >= ReserveBaseDrops + (OwnerCount × ReserveIncrementDrops)
2. **Total Supply**: Sum of all balances should equal totalCoins (100B XRP)
3. **Sequence Numbers**: Start with 1 or 2 for genesis accounts
4. **Index Hashing**: SHA-512-Half (first 256 bits) of namespace prefix + object-specific data

### Loading Genesis Ledger

```bash
rippled --ledgerfile /path/to/ledger.json
```

**Validator Configuration Required**: To maintain custom state after flag ledgers:

```ini
[voting]
reference_fee = 10
account_reserve = 2000000
owner_reserve = 200000
```

Values MUST match FeeSettings in genesis ledger.

### Best Practices

1. **Total Supply Management**: Designate one "genesis account" to hold remaining XRP
2. **Reserve Requirements**: Set ReserveBaseDrops high enough for testing (2-3 XRP)
3. **Fee Settings**: BaseFeeDrops of 10-1000 is typical for test networks
4. **Amendment Selection**: Include all enabled amendments from target network (Devnet/Testnet)
5. **Index Calculation**: Use SHA-512-Half with correct namespace prefixes

### Alternatives Considered

- **Manual JSON crafting**: Error-prone, difficult to maintain
- **Rippled export**: No official export tool for genesis ledgers
- **Third-party tools**: Limited availability and support

**Rejected because**: Programmatic generation using validated patterns is more reliable and maintainable.

---

## 2. MPT (Multi-Purpose Tokens) Creation

**Decision**: Use post-genesis transaction-based creation (NOT pre-generation)

**Rationale**: While theoretically possible to pre-generate MPT ledger objects, the transaction-based approach is safer, better documented, and ensures proper validation.

### MPT Overview

Multi-Purpose Tokens are a flexible token standard introduced via the MPTokensV1 amendment. Features include:
- Token locking (global or per-holder)
- Authorization controls (allow-listing)
- Transfer restrictions
- Clawback support
- Asset scale (decimal places)
- Maximum supply caps
- Transfer fees
- Metadata storage (up to 1024 bytes)

### Ledger Object Structure

#### MPTokenIssuance (Namespace: 0x7E)
Represents the token definition owned by issuer:
- Account (issuer address)
- Flags (immutable at creation)
- AssetScale (0-19, optional)
- MaximumAmount (optional)
- TransferFee (0-50000 basis points, optional)
- MPTokenMetadata (up to 2048 hex chars, optional)
- MPTokenIssuanceID (256-bit unique identifier)
- OutstandingAmount (total issued)

#### MPToken (Namespace: 0x74)
Represents individual holder balances:
- Account (holder address)
- MPTokenIssuanceID (reference to issuance)
- Amount (holder's balance)
- Flags (runtime state)

### Genesis Ledger Compatibility

**Answer: NOT RECOMMENDED**

**Evidence against pre-generation:**
1. Transaction-based creation model in xrpl-py library
2. Complex initialization (ID derivation from account + sequence)
3. No direct ledger object models in xrpl-py
4. Sequential dependencies (holder objects reference issuance ID)

**Evidence for pre-generation:**
1. Namespace bytes defined in codebase (0x74, 0x7E)
2. Pattern exists for other objects (AccountRoot, RippleState)
3. Amendment can be enabled in genesis

**Conclusion**: While theoretically possible, transaction-based creation is the safer, validated approach.

### Recommended Creation Process

**Step 1: Enable MPTokensV1 Amendment** (in genesis ledger)
```json
{
  "Amendments": [
    "950AE2EA4654E47F04AA8739C0B214E242097E802FD372D24047A89AB1F5EC38",
    ...
  ]
}
```

**Step 2: Create Funded Issuer Account** (in genesis ledger)
```json
{
  "Account": "rIssuerAddress...",
  "Balance": "100000000000",  // 100k XRP for reserves
  "Sequence": 1,
  "OwnerCount": 0
}
```

**Step 3: Submit MPTokenIssuanceCreate** (post-genesis)
```python
from xrpl.models.transactions import MPTokenIssuanceCreate, MPTokenIssuanceCreateFlag

create_tx = MPTokenIssuanceCreate(
    account="rIssuerAddress...",
    asset_scale=2,
    maximum_amount="1000000000",
    transfer_fee=100,
    flags=(
        MPTokenIssuanceCreateFlag.TF_MPT_CAN_TRANSFER |
        MPTokenIssuanceCreateFlag.TF_MPT_CAN_TRADE |
        MPTokenIssuanceCreateFlag.TF_MPT_REQUIRE_AUTH
    ),
    mptoken_metadata="7B226E616D65223A224D79546F6B656E227D"
)
```

**Step 4: Authorize Holders** (if TF_MPT_REQUIRE_AUTH set)
```python
from xrpl.models.transactions import MPTokenAuthorize

auth_tx = MPTokenAuthorize(
    account="rHolderAddress...",
    mptoken_issuance_id="ABCD1234..."
)
```

**Step 5: Distribute Tokens**
```python
from xrpl.models.transactions import Payment
from xrpl.models.amounts import MPTAmount

payment_tx = Payment(
    account="rIssuerAddress...",
    destination="rHolderAddress...",
    amount=MPTAmount(
        mpt_issuance_id="ABCD1234...",
        value="1000"
    )
)
```

### Dependencies

**Pre-Genesis** (can be in genesis ledger):
- Issuer account with sufficient XRP reserves
- Holder accounts (if distributing immediately)
- MPTokensV1 amendment enabled

**Post-Genesis** (requires running network):
- Network consensus active
- Transaction submission capability

### Implementation Approach

Create a post-genesis initialization script:
```python
# mpt_initializer.py
def initialize_mpts(config):
    # Wait for network consensus
    wait_for_consensus()

    # Create MPT issuances
    for mpt_config in config.mpts:
        create_mpt(mpt_config)

    # Authorize holders
    for holder in config.holders:
        authorize_holder(holder)

    # Distribute initial tokens
    distribute_tokens(config.distributions)
```

### Alternatives Considered

- **Genesis pre-generation**: Too complex, not validated
- **Manual transaction submission**: Not automated, error-prone

**Selected because**: Automated post-genesis initialization provides reliability while maintaining automation.

---

## 3. AMM (Automated Market Maker) Initialization

**Decision**: Create AMMs via post-genesis transactions (pre-generation NOT POSSIBLE)

**Rationale**: AMM creation involves asset transfers and complex state initialization that requires transaction execution semantics. Genesis ledgers cannot represent these operations.

### AMM Overview

Automated Market Makers provide on-ledger liquidity pools for decentralized trading:
- Constant-product formula (x * y = k)
- Trading pairs (XRP or fungible tokens)
- LP (Liquidity Provider) tokens
- Configurable trading fees (0-1%)
- Special AMM account holds pooled assets

### Ledger Object Structure

#### AMM Object (LedgerEntryType: "AMM", code: 121)
- Asset: First asset in trading pair
- Asset2: Second asset in trading pair
- Account: Special AMM account address
- TradingFee: Fee in basis points (0-1000)
- LPTokenBalance: Total outstanding LP tokens
- AuctionSlot: Auction slot holder info (optional)
- VoteSlots: Trading fee votes (optional)

#### Special AccountRoot
- Deterministically derived address from asset pair
- Holds actual asset balances
- Cannot be used for normal operations

#### Trust Lines
RippleState objects for token holdings (if not XRP)

### Genesis Ledger Compatibility

**Answer: NO - Not possible**

**Critical limitations:**
1. **Asset transfer semantics**: AMM creation transfers assets from creator to AMM account. Genesis ledgers have no "creator" performing transfers.
2. **Deterministic account generation**: AMM account address is computed algorithmically during transaction execution.
3. **LP token issuance**: Requires initial provider to receive LP tokens - no clear provider in genesis.
4. **Complex initialization**: Multiple ledger objects with bidirectional references must be created atomically.

**Transaction documentation explicitly states:**
> "Create a new Automated Market Maker (AMM) instance for trading a pair of assets... Creates both an AMM object and a special AccountRoot object."

### Creation Process (Post-Genesis Only)

**Step 1: Pre-fund Creator Account** (in genesis ledger)
```json
{
  "Account": "rAMMCreator...",
  "Balance": "100000000000",  // 100k XRP
  "Sequence": 1
}
```

**Step 2: Ensure Token Balances** (if using issued currencies)
Pre-generate trustlines in genesis ledger with sufficient balances.

**Step 3: Submit AMMCreate Transaction** (post-genesis)
```python
from xrpl.models.transactions import AMMCreate
from xrpl.models.amounts import IssuedCurrencyAmount

amm_tx = AMMCreate(
    account="rAMMCreator...",
    amount="1000000000",  // 1000 XRP
    amount2=IssuedCurrencyAmount(
        currency="USD",
        issuer="rIssuerAddress...",
        value="1000"
    ),
    trading_fee=500  // 0.5%
)
```

**Step 4: Verify Creation**
```python
from xrpl.models.requests import AMMInfo

amm_info = AMMInfo(
    asset=Currency(currency="USD", issuer="r..."),
    asset2=Currency(currency="XRP")
)
```

### Recommended Workflow

1. **Genesis Ledger**: Create accounts with sufficient XRP and token balances
2. **Post-Network Start**: Submit AMMCreate transactions (automated script)
3. **Timing**: Transactions processed in first few ledgers (5-10 seconds)

```python
# amm_initializer.py
def initialize_amms(config):
    wait_for_consensus()

    for amm_config in config.amm_pools:
        create_amm_pool(
            creator=amm_config.creator,
            asset1=amm_config.asset1,
            asset2=amm_config.asset2,
            amount1=amm_config.amount1,
            amount2=amm_config.amount2,
            fee=amm_config.trading_fee
        )
```

### Dependencies

**Pre-Genesis**:
- Creator accounts with sufficient XRP
- Issuer accounts for tokens
- Trust lines with sufficient limits and balances
- AMM amendment enabled

**Post-Genesis**:
- Network consensus achieved
- Minimum 4/5 validators online
- Transaction submission capability

### Implementation Notes

- AMMs are NOT pre-generable (unlike Accounts and Trustlines)
- Separate initialization step required after network start
- Can be automated as part of test environment setup
- Transactions will be included in first ledgers after genesis

### Alternatives Considered

- **Genesis pre-generation**: Not possible due to transaction semantics
- **Manual creation**: Not automated

**Selected because**: Automated post-genesis initialization is the only viable option.

---

## 4. Lending Protocol Primitives

**Decision**: Use Vault feature (when available) or compose existing primitives (Escrow, Trustlines, Oracles)

**Rationale**: XRPL has no official "Lending Protocol" as a native feature. The term "Lending Protocol primitives" likely refers to either the experimental Vault feature or a composition of existing XRPL features.

### Critical Finding

**No official native lending protocol exists in XRPL.**

### Option 1: Vault Feature (Experimental)

**Vault** is a new DeFi primitive found in xrpl-py binary codec definitions:

- **LedgerEntryType**: 132
- **Purpose**: Pooled asset management (deposit/withdrawal model)
- **Shares**: Represented as MPTokens
- **Assets**: Can hold XRP, IOUs, or MPTs
- **Status**: NOT in amendment list (as of Sept 2025) - experimental/unreleased

#### Vault Transaction Types

1. **VaultCreate** (65): Create vault with asset type, withdrawal policy, metadata
2. **VaultSet** (66): Update vault configuration
3. **VaultDeposit**: Add assets, receive shares
4. **VaultWithdraw**: Redeem shares for assets
5. **VaultDelete** (67): Remove vault
6. **VaultClawback**: Operator reclaims assets

#### Genesis Compatibility

**Answer: UNCERTAIN - Theoretically YES, but...**

- Amendment not yet in activation list
- Ledger object structure not documented
- No working examples available
- Would require proper index calculation

**Recommendation**: Wait for Vault amendment to be officially released before implementing.

### Option 2: Existing Primitives for Lending

Build lending functionality using production-ready features:

#### Escrow (for time-locked collateral)
```json
{
  "LedgerEntryType": "Escrow",
  "Account": "borrower_address",
  "Destination": "lender_address",
  "Amount": "collateral_amount",
  "FinishAfter": loan_due_timestamp,
  "index": "..."
}
```

**Genesis Compatible**: YES - Can be pre-generated

#### RippleState/Trustlines (for debt tokens)
```json
{
  "LedgerEntryType": "RippleState",
  "HighLimit": {"currency": "DEBT", "issuer": "lender", "value": "limit"},
  "LowLimit": {"currency": "DEBT", "issuer": "borrower", "value": "0"},
  ...
}
```

**Genesis Compatible**: YES - Already implemented in codebase

#### Oracle (for price feeds)
- **LedgerEntryType**: 128
- Provides on-chain price data
- Critical for collateralized lending (liquidation triggers)

**Genesis Compatible**: Needs research

#### Check (for deferred payments)
- **LedgerEntryType**: 67
- Can be used for loan disbursement/repayment

**Genesis Compatible**: YES

### Recommended Implementation

**For Initial Version**: Use trustlines to represent lending relationships

```python
def generate_lending_primitives(config):
    # Create issuer account for "Lending Protocol"
    lending_protocol_account = create_account("rLendingProtocol...")

    # Pre-generate trustlines
    for lender, borrower in config.lending_pairs:
        trustline = generate_trustline(
            hi=lender_address,
            lo=borrower_address,
            currency="DEBT",
            hi_amount=lending_limit,
            lo_amount=0
        )
        ledger_objects.append(trustline)
```

**For Future Enhancement**: Add Vault support when amendment becomes available

```python
def check_vault_availability():
    amendments = get_amendments('devnet')
    vault_amendment = [a for a in amendments if 'vault' in a.name.lower()]
    return len(vault_amendment) > 0

if check_vault_availability():
    generate_vault_objects(config)
else:
    generate_trustline_based_lending(config)
```

### Dependencies

**Trustline-Based Approach**:
- Lender and borrower accounts in genesis
- Optional: Oracle objects for price feeds
- Optional: Escrow objects for collateral

**Vault-Based Approach** (future):
- Vault amendment enabled
- Vault ledger object structure documented
- Index calculation algorithm available
- MPToken amendment (for vault shares)

### Implementation Priority

1. **Phase 1**: Implement trustline-based lending (production-ready)
2. **Phase 2**: Monitor Vault amendment status
3. **Phase 3**: Implement Vault support when available

### Action Items

1. Clarify with stakeholder what "Lending Protocol primitives" means
2. Query devnet/testnet for Vault amendment availability: `feature` RPC command
3. If Vault exists, test creation and document structure
4. Implement trustline-based approach as interim solution

### Alternatives Considered

- **Wait for Vault**: Blocks feature development
- **Custom off-ledger solution**: Not using XRPL primitives
- **Third-party protocol**: Integration complexity

**Selected because**: Trustlines provide immediate functionality while allowing future Vault integration.

---

## 5. Validator Identity and Configuration

**Decision**: Use xrpl-py for key generation, rippled.cfg template for configuration, inline UNL for test networks

**Rationale**: The existing codebase implements a robust, validated pattern for validator setup that follows XRPL best practices.

### Key Generation

**Preferred Method**: xrpl-py library (Python-native)
```python
def keygen_xrpl() -> Tuple[PublicKey, ValidatorToken]:
    seed = xrpl.core.keypairs.generate_seed(algorithm=xrpl.CryptoAlgorithm.SECP256K1)
    pub_hex, _ = xrpl.core.keypairs.derive_keypair(seed, validator=True)
    token = f"[validation_seed]\\n{seed}"
    pub_key = xrpl.core.addresscodec.encode_node_public_key(bytes.fromhex(pub_hex))
    return pub_key, token
```

**Alternative**: Docker-based validator key tool
```python
def keygen_docker():
    res = subprocess.run(["docker", "run", "legleux/vkt"], capture_output=True, text=True, check=True)
    # Parse output for public key and token
    return pub_key, token
```

**Key Formats**:
- Validation Seed: Base58 starting with `s` (e.g., `ssFMztqLbZTgLti9n9XTyMqLBAkKy`)
- Public Key: Node format starting with `n9` (e.g., `n9M8j6NSHEu1b8ieDgiBgwLev8bFVqYWhJvzEoLvKdgSvJmbLN3F`)
- Algorithm: SECP256K1 (standard)

### Configuration Files

**Primary File**: `rippled.cfg`

**Essential Sections**:

1. **Server Ports**:
```ini
[port_peer]
port = 51235
ip = 0.0.0.0
protocol = peer

[port_rpc_admin_local]
port = 5005
ip = 0.0.0.0
admin = [0.0.0.0]
protocol = http

[port_ws_admin_local]
port = 6006
ip = 0.0.0.0
admin = [0.0.0.0]
protocol = ws
```

2. **Database Configuration**:
```ini
[node_db]
type = NuDB
path = /var/lib/rippled/db/nudb

[database_path]
/var/lib/rippled/db

[ledger_history]
full
```

3. **Validator-Specific Sections**:
```ini
[validators]
n9M8j6NSHEu1b8ieDgiBgwLev8bFVqYWhJvzEoLvKdgSvJmbLN3F
n9LSEbZcmzs7RmvkS1CxixnmycGT43vKf7bs9rZonbMMQ2ohmapx
n9MNTKaR4rQNgnxnp9vYNRcL4iZrxEy63oKqTpmvGmDYp1PRPAPi
n9LBAoqmEeN9R4qXCCx5avCHzGt45QMJjDViNGvQhroQA5QxjNXD
n9LouvqJxS6ZmTWWGGaC6xRxV6idSxYuGbJYMkc8SQXSWJAoXA9v

[ips_fixed]
val1 51235
val2 51235
val3 51235
val4 51235

[voting]
reference_fee = 10
account_reserve = 2000000
owner_reserve = 200000

[validation_seed]
ssFMztqLbZTgLti9n9XTyMqLBAkKy
```

**Dynamic Generation Pattern**:
```python
def ips_fixed_block(self, who_index: int | None) -> str:
    # For validator i, include all validators except self i
    # For non-validator node, include all validators
    lines = []
    for j in range(self.num_validators):
        if who_index is not None and j == who_index:
            continue
        lines.append(f"{self.validator_name}{j} {self.peer_port}")
    return "\\n[ips_fixed]\\n" + "\\n".join(lines) + "\\n"
```

### UNL Configuration

**For Private Test Networks**: Inline `[validators]` section in rippled.cfg

**Key Principles**:
1. All nodes share identical UNL
2. List all validator public keys (n9... format)
3. No external validators.txt needed for test networks
4. Consensus requires 80% quorum (4/5 validators for 5-node network)

**Full Mesh Peering**: Use `[ips_fixed]` for direct validator connections

### Genesis Ledger Reference

**Bootstrap Validator** (loads genesis):
```bash
rippled --ledgerfile /ledger.json
```

**Other Validators** (sync from network):
```bash
rippled --net
```

**Docker Compose Pattern**:
```yaml
val0:
  command: ["--ledgerfile", "/ledger.json"]
  volumes:
    - ./ledger.json:/ledger.json
  healthcheck:
    test: ["CMD", "rippled", "--silent", "ping"]

val1:
  command: ["--net"]
  depends_on:
    val0:
      condition: service_healthy
```

**Critical Requirement**: Voting parameters must match FeeSettings in genesis ledger:
```ini
[voting]
reference_fee = 10             # Must match BaseFeeDrops
account_reserve = 2000000      # Must match ReserveBaseDrops
owner_reserve = 200000         # Must match ReserveIncrementDrops
```

### Network Settings

**Ports**:
- Peer Protocol: 51235 (internal validator communication)
- RPC Admin: 5005 (HTTP JSON-RPC)
- WebSocket Admin: 6006 (WebSocket API)

**Consensus Requirements**:
- 5 validators: Need 4 online (80%)
- Byzantine fault tolerance: 1 failure tolerated
- Ledger close time: 3-5 seconds typical

### Best Practices

1. **Identity Generation**: Unique validation seeds per validator, SECP256K1 algorithm
2. **Configuration Management**: Template-based generation, validate parameters
3. **Network Topology**: Full mesh via [ips_fixed] for 5-10 validators
4. **Economic Parameters**: Identical [voting] section across all validators
5. **Startup Order**: Bootstrap validator first, others depend on health check
6. **Testing**: Verify consensus with validator failures, confirm fee/reserve persistence

### Implementation Reference

Working implementation at:
- Key generation: `src/generate_ledger/rippled_cfg.py`
- Config template: `src/generate_ledger/rippled.cfg`
- Test network: `testnet/docker-compose.yml`
- Validator configs: `testnet/volumes/val[0-4]/rippled.cfg`

---

## 6. Docker Networking for XRPL Validators

**Decision**: Use custom Docker bridge networks with DNS-based peer discovery

**Rationale**: Custom bridge networks provide isolation, automatic DNS resolution, and optimal performance for validator consensus in containerized environments.

### Network Architecture

**Network Mode**: Custom bridge network

```yaml
networks:
  xrpl_net:
    name: xrpl_net
    driver: bridge
```

**Benefits**:
- Container DNS resolution (validators connect via hostnames)
- Network isolation (multiple test networks don't interfere)
- No port conflicts (internal ports identical across networks)
- Security (isolated from host and other networks)
- Flexibility (easy to add/remove validators)

**Why NOT host mode**: Port conflicts, no isolation, security risks

### Port Configuration

**Rippled Port Types**:

1. **Peer Protocol** (51235): Validator-to-validator - Internal only
2. **HTTP RPC** (5005): Administrative commands - Expose for external access
3. **WebSocket** (6006): Subscriptions - Expose for external access

**Exposure Strategy**:
- Bootstrap validator (val0): Expose RPC/WS with offsets (5006:5005, 6007:6006)
- Hub node (rippled): Expose standard ports (5005:5005, 6006:6006)
- Other validators: No external exposure (internal only)

**Port Mapping Pattern**:
```yaml
ports:
  - "${VAL0_RPC_PORT:-5006}:5005"
  - "${VAL0_WS_PORT:-6007}:6006"
```

### Container Discovery

**DNS-Based Discovery**:
```ini
[ips_fixed]
val0 51235
val1 51235
val2 51235
val3 51235
val4 51235
```

Custom bridge network automatically resolves service names to container IPs.

**Validator Identification**:
```ini
[validators]
n9M8j6NSHEu1b8ieDgiBgwLev8bFVqYWhJvzEoLvKdgSvJmbLN3F
n9LSEbZcmzs7RmvkS1CxixnmycGT43vKf7bs9rZonbMMQ2ohmapx
...
```

**Bootstrap Process**:
1. val0 starts with `--ledgerfile` (loads genesis)
2. Health check confirms val0 ready
3. Other validators start with `--net` (sync from network)

```yaml
depends_on:
  val0:
    condition: service_healthy
```

### Isolation Strategy

**Multi-Layer Isolation**:

1. **Network-level**: Unique custom bridge networks per test environment
2. **Container naming**: Unique names to avoid conflicts
3. **Port mapping**: Different host ports per network
4. **Volume isolation**: Separate volume directories
5. **Configuration isolation**: Unique validator keys, UNL, genesis ledgers

**Multiple Test Networks Pattern**:
```
project/
├── testnet1/
│   ├── docker-compose.yml  (network: xrpl_net_test1)
│   ├── ledger.json
│   └── volumes/
├── testnet2/
│   ├── docker-compose.yml  (network: xrpl_net_test2)
│   ├── ledger.json
│   └── volumes/
```

### Volume Mounts

**Required Mounts**:

1. **Configuration** (`/etc/opt/ripple`):
```yaml
volumes:
  - ./volumes/val0:/etc/opt/ripple
```

2. **Genesis Ledger**:
```yaml
volumes:
  - ./ledger.json:/ledger.json
```

**Optional but Recommended**:

3. **Database persistence** (`/var/lib/rippled/db`):
```yaml
volumes:
  - ./data/val0:/var/lib/rippled/db
```

4. **Logs** (`/var/log/rippled`):
```yaml
volumes:
  - ./logs/val0:/var/log/rippled
```

**For ephemeral test networks**: Config and genesis only (current approach)

### Docker Compose Structure

**Recommended Pattern**:
```yaml
services:
  val0:
    image: rippleci/rippled:develop
    container_name: val0
    hostname: val0
    command: ["--ledgerfile", "/ledger.json"]
    ports:
      - "5006:5005"
      - "6007:6006"
    healthcheck:
      test: ["CMD", "rippled", "--silent", "ping"]
      start_period: 10s
      interval: 10s
      timeout: 5s
      retries: 3
    volumes:
      - ./volumes/val0:/etc/opt/ripple
      - ./ledger.json:/ledger.json
    networks:
      - xrpl_net
    restart: unless-stopped

  val1:
    image: rippleci/rippled:develop
    container_name: val1
    hostname: val1
    command: ["--net"]
    depends_on:
      val0:
        condition: service_healthy
    volumes:
      - ./volumes/val1:/etc/opt/ripple
      - ./ledger.json:/ledger.json
    networks:
      - xrpl_net
    restart: unless-stopped

  # val2, val3, val4 similar to val1

  rippled:
    image: rippleci/rippled:develop
    container_name: rippled
    hostname: rippled
    ports:
      - "5005:5005"
      - "6006:6006"
    depends_on:
      val0:
        condition: service_healthy
    volumes:
      - ./volumes/rippled:/etc/opt/ripple
    networks:
      - xrpl_net
    restart: unless-stopped

networks:
  xrpl_net:
    name: ${NETWORK_NAME:-xrpl_net}
    driver: bridge
```

**Dynamic Generation**: Existing implementation in `src/generate_ledger/compose.py`

### Best Practices

**Performance**:
- Node sizing: `[node_size] huge` for validators
- Resource limits: 2-4GB memory per validator
- Database: NuDB (already configured)
- Ledger history: `full` for validators

**Security**:
- Admin access: `admin = [0.0.0.0]` (test networks only)
- SSL verification: Disabled for test networks
- Peer privacy: Disabled (all peers known)
- Compression: Disabled (reduces CPU in local testing)

**Debugging**:
- Log levels: `info` severity appropriate
- Log access: Mount log directories
- Container logs: `docker-compose logs -f val0`
- Health monitoring: `docker exec val0 rippled --silent ping`
- Network inspection: `docker network inspect xrpl_net`

**Consensus Testing**:
```bash
# Check validator
docker exec rippled rippled server_info | jq .result.info.pubkey_validator

# Check peers
docker exec val0 rippled peers

# Check consensus
docker exec rippled rippled consensus_info

# Check ledger progression
docker exec rippled rippled ledger_closed
```

### Implementation Reference

Working implementation:
- Compose generation: `src/generate_ledger/compose.py`
- Rippled config: `src/generate_ledger/rippled_cfg.py`
- Working setup: `testnet/docker-compose.yml`

**Current implementation already follows best practices** for Docker networking with XRPL validators.

---

## Summary of Recommendations

| Component | Approach | Genesis Compatible | Timeline |
|-----------|----------|-------------------|----------|
| **Accounts** | Pre-generate AccountRoot objects | ✅ YES | Immediate |
| **Trustlines** | Pre-generate RippleState objects | ✅ YES | Immediate |
| **FeeSettings** | Pre-generate with fixed index | ✅ YES | Immediate |
| **Amendments** | Pre-generate with enabled list | ✅ YES | Immediate |
| **MPT** | Post-genesis transactions | ⚠️ Not Recommended | Phase 2 |
| **AMM** | Post-genesis transactions | ❌ NO | Phase 2 |
| **Lending** | Trustlines initially, Vault later | ⚠️ Partial | Phase 1/3 |
| **Validator Config** | Template-based generation | ✅ YES | Immediate |
| **Docker Network** | Custom bridge with DNS | ✅ YES | Immediate |

## Implementation Phases

**Phase 1 (Immediate)**:
- Generate genesis ledger with Accounts, Trustlines, FeeSettings, Amendments
- Generate validator configurations with keys and UNL
- Generate docker-compose with custom bridge network
- Implement trustline-based lending primitives

**Phase 2 (Post-Genesis Initialization)**:
- Automated MPT creation script
- Automated AMM creation script
- Run after network consensus achieved (5-10 seconds)

**Phase 3 (Future Enhancement)**:
- Monitor Vault amendment status
- Implement Vault-based lending when available
- Additional ledger object types as needed

## References

**Analyzed Files**:
- Genesis ledger examples: `testnet/ledger.json`, `ledger_also_works.json`
- Account generation: `src/generate_ledger/accounts.py`
- Trustline generation: `src/generate_ledger/trustlines.py`
- Validator config: `src/generate_ledger/rippled_cfg.py`
- Docker compose: `src/generate_ledger/compose.py`
- Namespace definitions: `src/generate_ledger/models/ledger.py`
- Index calculation: `src/generate_ledger/indices.py`
- Test network: `testnet/docker-compose.yml`

**External Documentation**:
- XRPL.org: Ledger formats, validator setup, consensus protocol
- xrpl-py library: Transaction and ledger object models
- Docker documentation: Networking, compose best practices
