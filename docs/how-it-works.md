# How It Works

Every object in an XRPL ledger is identified by a 256-bit **index** (also called a key or hash). The index is computed deterministically from the object's properties using SHA-512 Half -- the first 32 bytes of a SHA-512 digest. Each object type uses a unique **namespace byte** prefix to avoid collisions.

This page explains how `generate_ledger` derives each object type that can appear in a genesis ledger.

## Core Primitives

| Primitive       | Definition                          | Used For                   |
| --------------- | ----------------------------------- | -------------------------- |
| **SHA512Half**  | First 32 bytes of SHA-512           | All ledger object indices  |
| **RIPESHA**     | RIPEMD-160(SHA-256(data))           | Account ID from public key |
| **Base58Check** | Base58 with version byte + checksum | Address/seed encoding      |

## AccountRoot

Every funded account has an `AccountRoot` entry.

**Derivation:**

1. Generate a random 16-byte seed
2. Derive an ed25519 keypair: `SHA512Half(seed)` → private scalar → public key
3. Compute account ID: `RIPESHA(0xED || public_key)` → 20 bytes
4. Encode as classic address: `Base58Check(account_id)` → `r...` string

**Index:** `SHA512Half(0x0061 + account_id)`

**Key fields:**

- `Balance` -- XRP in drops (1 XRP = 1,000,000 drops)
- `Sequence` -- 2 for regular accounts, 0 for pseudo-accounts (AMM)
- `OwnerCount` -- number of objects this account owns (trustlines, AMM positions, etc.)
- `Flags` -- `0x00800000` (lsfDefaultRipple) for token issuers, `0` for regular accounts

## RippleState (Trustlines)

A `RippleState` represents a trust relationship between two accounts for a specific currency.

**Derivation:**

1. Take two account addresses and a currency code
2. Decode both to 20-byte account IDs
3. Order IDs lexicographically → (low, high)
4. Encode currency as 20 bytes (3-letter ASCII padded at bytes 12-14)

**Index:** `SHA512Half(0x0072 + low_account_id + high_account_id + currency_bytes)`

**Key fields:**

- `LowLimit` / `HighLimit` -- trust limits for each party
- `Balance` -- always `"0"` in genesis (no pre-funding of issued tokens)
- `Flags` -- `0x00020000` (lsfLowReserve) for normal trustlines, `0x01000000` (lsfAMMNode) for AMM trustlines

**Balance sign convention:** Positive means the low-ordered account holds the balance; negative means the high-ordered account holds it.

## DirectoryNode

Each account has one `DirectoryNode` (owner directory) listing all objects it owns.

**Index:** `SHA512Half(0x004F + account_id)`

**Key fields:**

- `Owner` -- the account address
- `Indexes` -- sorted list of owned object indices (XRPL requires lexicographic ordering)

During ledger assembly, directory entries from trustlines, AMM objects, and MPTokens are consolidated into a single DirectoryNode per account with all Indexes merged and sorted.

## AMM

An Automated Market Maker pool consists of multiple linked objects.

### AMM Entry

**Derivation:**

1. Define two assets (XRP or issued currency)
2. Convert each asset to 40 bytes: `issuer_id (20B) + currency_code (20B)` (XRP = 40 zero bytes)
3. Order assets lexicographically

**Index:** `SHA512Half(0x0041 + min_asset_bytes + max_asset_bytes)`

### AMM Pseudo-Account

The AMM itself is represented by a pseudo-account derived from the AMM index:

```
address = Base58Check(RIPESHA(0x0000 + 32_zero_bytes + amm_index_bytes))
```

This pseudo-account has `Sequence = 0` and flags `0x01900000` (lsfDisableMaster + lsfDefaultRipple + lsfDepositAuth).

### LP Token Currency

The LP token currency code is derived from the two asset currencies (not the issuers):

```
lp_currency = 0x03 + first_19_bytes(SHA512Half(min_currency + max_currency))
```

### LP Token Amount

Computed as the geometric mean of the two deposit amounts:

```
lp_tokens = sqrt(asset1_amount * asset2_amount)
```

### Associated Objects

Each AMM pool creates:

- 1 `AMM` entry
- 1 `AccountRoot` (pseudo-account)
- 1 `DirectoryNode` for the pseudo-account
- 1 `RippleState` per non-XRP asset (AMM ↔ issuer, with lsfAMMNode flag)
- 1 `RippleState` for LP tokens (if a creator is specified)

## Amendments

A single `Amendments` entry lists all enabled protocol amendments.

**Index:** Fixed at `7DB0788C020F02780A673DC74757F23823FA3014C1866E72CC4CD8B226CD6EF4`

Each amendment's hash is computed from its name:

```
amendment_hash = SHA512Half("AmendmentName".encode("ascii")).hex().upper()
```

Amendment sources:

- **release** profile -- queries mainnet xrpld RPC for actually-enabled amendments (falls back to bundled snapshot)
- **develop** profile -- parses `features.macro` from the xrpld source to get all supported amendments
- **custom** profile -- user-provided JSON file

## MPTokenIssuance

A Multi-Purpose Token issuance defines a new token type. Requires the `MPTokensV1` amendment (enabled on mainnet since 2025-10-01).

**Derivation:**

1. Combine a per-issuer sequence number with the issuer's account ID
2. Build a 24-byte MPTID: `big_endian_u32(sequence) + account_id`

**Index:** `SHA512Half(0x007E + mptid)`

**Key fields:**

- `Issuer` -- the issuing account
- `Sequence` -- per-issuer counter (not the account sequence)
- `OutstandingAmount` -- sum of all holder balances (computed from holders)
- `MaximumAmount`, `AssetScale`, `TransferFee`, `MPTokenMetadata` -- optional

## MPToken

An individual holder's balance of an MPT. One entry per holder per issuance.

**Index:** `SHA512Half(0x0074 + issuance_index + holder_account_id)`

**Key fields:**

- `Account` -- holder address
- `MPTokenIssuanceID` -- 48-character hex MPTID
- `MPTAmount` -- amount held

## FeeSettings

Controls the network's fee parameters. One entry per ledger.

**Key fields:**

- `BaseFeeDrops` -- base transaction fee (default: 121 drops)
- `ReserveBaseDrops` -- account reserve (default: 2,000,000 drops = 2 XRP)
- `ReserveIncrementDrops` -- per-object reserve increment (default: 666 drops)

## Index Reference

| Object          | Namespace | Formula                                          |
| --------------- | --------- | ------------------------------------------------ |
| AccountRoot     | `0x0061`  | SHA512Half(0x0061 + account_id)                  |
| RippleState     | `0x0072`  | SHA512Half(0x0072 + low_id + high_id + currency) |
| DirectoryNode   | `0x004F`  | SHA512Half(0x004F + account_id)                  |
| AMM             | `0x0041`  | SHA512Half(0x0041 + min_asset + max_asset)       |
| MPTokenIssuance | `0x007E`  | SHA512Half(0x007E + mptid)                       |
| MPToken         | `0x0074`  | SHA512Half(0x0074 + issuance_index + holder_id)  |
| Amendments      | --        | Fixed: `7DB0788C...CD6EF4`                       |
