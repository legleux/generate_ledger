# generate_ledger Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-01-27

## Active Technologies

- Python 3.12+ (currently 3.13, supports 3.13t free-threaded) + xrpl-py (4.2.0+), typer/click (CLI), pydantic (validation), ruamel-yaml (config), httpx (networking), base58 (encoding) (001-xrpl-ledger-generator)
- Native crypto backends (optional, for benchmarking): pynacl (ed25519), coincurve/fastecdsa (secp256k1)

## Project Structure

```text
src/generate_ledger/
├── models/              # Data models (ledger, namespace, ripplestate)
├── services/            # Business logic (ledger, config, compose services)
├── cli/                 # CLI commands (main, ledger, rippled_cfg, compose, auto)
├── commands/            # Command implementations (ledger_writer, config, compose_writer)
├── utils/               # Utilities (config, paths, merging)
├── topo/                # Network topology
├── accounts.py          # Account generation
├── trustlines.py        # Trustline generation (✅ COMPLETE - commit 955aae3)
├── amm.py               # AMM pool generation (✅ COMPLETE - 2026-01-21)
├── amendments.py        # XRPL amendments
├── indices.py           # Ledger index calculations (includes AMM index, account, LP token)
├── ledger_builder.py    # Ledger assembly (supports trustlines + AMM)
├── rippled_cfg.py       # Validator config generation
└── compose.py           # Docker compose generation

tests/
├── cli/                 # CLI tests
├── lib/                 # Library/unit tests
└── data/                # Test fixtures

scripts/
├── bench_accounts.py    # Account + trustline benchmark (parallel strategies, native crypto, binary seeds)
└── README.md            # Benchmark documentation
```

## Commands

```bash
# Run tests
pytest

# Lint code
ruff check .

# Generate complete environment
gen auto --output-dir ./testnet

# Generate ledger only
gen ledger --accounts 50 --output ./ledger.json

# Generate validators
gen validators --count 5 --output-dir ./volumes

# Generate docker compose
gen compose --validators 5 --output ./docker-compose.yml

# Benchmark account + trustline generation (see scripts/README.md for details)
uv run scripts/bench_accounts.py --info                                    # Check available backends
uv run scripts/bench_accounts.py -n 10000 --algo ed25519 --mode mp         # Benchmark accounts
uv run scripts/bench_accounts.py -n 1000 --trustlines --mode mp            # Benchmark accounts + trustlines
uv run scripts/bench_accounts.py -n 100 --trustlines --topology mesh       # Benchmark mesh topology
uv run scripts/bench_accounts.py -n 100000 --seeds-only --save-seeds s.bin # Generate seeds (binary, default)
uv run scripts/bench_accounts.py -n 100000 --seeds-only --save-seeds s.txt --seeds-text  # Seeds as text

# With Python 3.13t (free-threaded/no-GIL) for thread parallelism
uv run --no-project --with xrpl-py --with pynacl -p 3.13t scripts/bench_accounts.py -n 10000 --algo ed25519 --mode thread
```

## Code Style

Python 3.12+ (currently 3.13): Follow standard conventions

## Working Principles

**CLAUDE.md Maintenance**: This file MUST be updated continuously as work progresses:
- ✅ After completing any user story or phase
- ✅ After making significant architectural changes
- ✅ At the end of major work sessions
- ✅ When scope or priorities change
- ❌ NOT as a separate task - it's part of the completion criteria for all work

**What to Update**:
- Implementation Status: Mark phases/stories as complete
- Recent Changes: Add dated entries for completed work
- Next Session Options: Update based on current state
- Project Structure: Update if new modules are added

## Implementation Status (Feature 001-xrpl-ledger-generator)

### ✅ MVP Complete (v1.0)
- **User Story 1 (P1)**: Accounts + Trustlines generation ✅
  - Account generation with custom balances and identifiers
  - Trustline generation with RippleState + DirectoryNode objects
  - Reserve validation and credential export
  - CLI: `gen ledger` command

- **User Story 2 (P2)**: Validator configurations ✅
  - Validator key generation and UNL management
  - rippled.cfg generation with voting sections
  - Fixed peer connections (ips_fixed)
  - CLI: `gen validators` command

- **User Story 3 (P3)**: Docker deployment ✅
  - docker-compose.yml generation
  - Bridge networking with isolated containers
  - Validator dependency ordering (val0 bootstrap)
  - CLI: `gen compose` and `gen auto` commands

### ✅ AMM Support Complete (v2.0 Feature)
- **User Story 5 (P5)**: AMM (Automated Market Maker) support ✅
  - AMM ledger object generation with proper index calculation
  - AMM pseudo-account (AccountRoot) with AMMID link and XRP balance
  - LP token currency derivation (0x03 + SHA512Half of sorted currencies)
  - LP token trustline (RippleState) for liquidity providers
  - Asset trustlines (RippleState) for deposited tokens with lsfAMMNode flag
  - DirectoryNode consolidation for all AMM-related objects (both AMM and issuer directories)
  - Auction slot (with valid Expiration) and vote slot initialization
  - Integration with LedgerConfig via AMMPoolConfig
  - **Automatic lsfDefaultRipple**: Accounts used as issuers for AMM pool assets (`-a` flag) automatically have `lsfDefaultRipple` (0x00800000) set on their AccountRoot

### 🔴 Planned for v2.0
- **User Story 4 (P4)**: MPT (Multi-Purpose Tokens) support
- **User Story 6 (P6)**: Vault/Lending protocol support

### 🟡 In Progress
- Phase 9: Integration & Testing (tasks T058-T075)
- Phase 10: Polish & UX improvements (tasks T076-T085)
- Phase 11: Performance validation (tasks T086-T090)

## Recent Changes

- 2026-01-28: Critical AMM bug fixes
  - **lsfAMMNode flag fix**: Changed from 0x02000000 (lsfLowDeepFreeze) to 0x01000000 (lsfAMMNode)
    - The wrong flag was freezing asset trustlines, blocking two-asset AMMDeposit transactions
    - Single-asset XRP deposits worked, but any USD transfers failed with `temBAD_AMOUNT`
  - **AMM account derivation fix**: Removed erroneous SHA512Half step
    - Was: `RIPESHA(SHA512Half(i + parentHash + ammIndex))` ← WRONG
    - Now: `RIPESHA(i + parentHash + ammIndex)` ← Correct (matches rippled)
    - Fixed `amm_info` returning "Account malformed" errors
  - Both fixes required to enable full AMMDeposit functionality on pre-generated ledgers

- 2026-01-27: CLI options for trustlines and AMM pools + AMM bug fixes
  - New CLI flags: `--num-trustlines`, `--trustline/-t`, `--currencies`, `--trustline-limit`
  - New CLI flags: `--amm-pool/-a` for AMM pool creation
  - Parser module (`cli/parsers.py`) for colon-delimited CLI formats
  - AMM fixes: AuctionSlot.Expiration, AMM account XRP balance, OwnerCount
  - AMM fixes: Asset trustlines now in both AMM and issuer directories
  - Automatic `lsfDefaultRipple` flag for AMM token issuers

- 2026-01-27: Trustline benchmarking + binary seed format (`scripts/bench_accounts.py`)
  - Trustline object generation benchmark (RippleState + 2 DirectoryNodes)
  - Self-contained index calculations (no generate_ledger dependency for benchmarks)
  - Topology strategies: star, ring, mesh, random
  - CLI: `--trustlines`, `--topology`, `--currencies`, `--trustlines-only`
  - Binary seed format (default): ~48% size of text, auto-detected on load
  - CLI: `--seeds-text` for text format compatibility
  - FallbackBackend now generates hex seeds (converts to base58 internally)

- 2026-01-27: Account generation benchmark script (`scripts/bench_accounts.py`)
  - Parallel execution modes: sequential, multiprocessing, threading, hybrid
  - Native crypto backends: PyNaCl (ed25519 ~50k/sec), coincurve/fastecdsa (secp256k1 ~15k/sec)
  - Python 3.13t (free-threaded/no-GIL) support for true thread parallelism
  - Seed management: `--seeds-file`, `--save-seeds`, `--seeds-only` for reproducible benchmarks
  - Fixed hybrid mode pickling issue (moved process_batch to module level)
  - Modular architecture: CryptoBackend + AddressEncoder abstractions

- 2026-01-21: AMM (Automated Market Maker) implementation completed
  - Added `amm.py` with full AMM pool generation
  - AMM index calculation: `SHA512Half(0x0041 + asset1 + asset2)`
  - AMM account derivation: `RIPESHA(SHA512Half(0 + parentHash + ammIndex))`
  - LP token currency: `0x03 + first_19_bytes(SHA512Half(min(cur1), max(cur2)))`
  - LP token accounting with RippleState trustlines
  - Integration with `ledger_builder.py` and `LedgerConfig`
  - Tasks T042-T049 completed

- 2026-01-20: Trustlines implementation completed (commit 955aae3)
  - Full RippleState object generation with DirectoryNode consolidation
  - Transaction ID generation for proper ledger state
  - Integration with ledger assembly
  - OwnerCount calculation for trustline holders

- 2026-01-20: Spec documentation synchronized
  - Generated tasks.md with 90 tasks (33 complete, 57 pending)
  - Updated spec.md status to "MVP Complete (US1-3)"
  - Clarified v1.0 vs v2.0 scope (Accounts/Trustlines in v1.0, MPT/AMM/Vault in v2.0)
  - Resolved all plan.md technical clarifications
  - Added edge case validation tasks (T071-T075)
  - Added performance validation tasks (T086-T090)

- 2025-12-10: Initial setup with Python 3.12+ (currently 3.13) + xrpl-py (4.2.0+), typer/click (CLI), pydantic (validation), ruamel-yaml (config), httpx (networking), base58 (encoding)

## Next Session Options

### Option A - Production Hardening (Recommended for v1.0 Release)
Focus on validating and polishing existing MVP functionality:
1. Execute Phase 9: Integration & Testing (T058-T075)
   - Test complete environment generation
   - Test accounts + trustlines generation
   - Test validator consensus
   - Test edge cases (validation failures, conflicts, mismatches)
2. Execute Phase 10: Polish (T076-T085)
   - Add comprehensive error messages
   - Implement JSON output mode
   - Add security warnings to credential files
   - Create example configurations
3. Execute Phase 11: Performance Validation (T086-T090)
   - Validate 5-minute generation requirement (SC-001)
   - Scale testing (100/500/1000 accounts + trustlines)
4. Release v1.0 MVP

### Option B - Advanced Features (v2.0 Development)
Implement extended ledger object support:
1. Phase 6: MPT Support (tasks T034-T041)
   - Research MPT ledger object structure
   - Implement MPTokenIssuance and MPToken generation
   - Add CLI options for MPT
2. ~~Phase 7: AMM Support (tasks T042-T049)~~ ✅ COMPLETE
3. Phase 8: Vault Support (tasks T050-T057)
   - Research Vault ledger object structure
   - Implement single-asset vault generation
   - Add share token accounting
4. Then execute Phases 9-11 for full validation

### Key Files to Reference
- Spec: `specs/001-xrpl-ledger-generator/spec.md`
- Tasks: `specs/001-xrpl-ledger-generator/tasks.md`
- Plan: `specs/001-xrpl-ledger-generator/plan.md`
- Data Model: `specs/001-xrpl-ledger-generator/data-model.md`
- CLI Contract: `specs/001-xrpl-ledger-generator/contracts/cli-interface.md`

## Next TODOs

### 1. Test AMM Fixes (PRIORITY)
Verify the 2026-01-28 AMM bug fixes work correctly:

```bash
# Generate ledger with AMM
gen ledger -n 2 -o testnet -t "0:1:USD:1000000000" -a "XRP:USD:0:1000000000000:1000000:500:0"

# Start rippled, then test:
# 1. amm_info should return valid AMM (no "Account malformed")
# 2. Single-asset XRP deposit should succeed
# 3. Two-asset deposit (XRP + USD) should succeed (this was broken before!)
# 4. Bob (non-issuer) two-asset deposit should also work
```

**Specific tests needed**:
- `amm_info` with AMM account address returns valid response
- `AMMDeposit` with `tfSingleAsset` (XRP only) succeeds
- `AMMDeposit` with `tfTwoAsset` (XRP + USD) succeeds ← **This was the broken case**
- Verify asset trustline has `lsfAMMNode` (0x01000000), NOT frozen
- Verify `account_lines` for AMM shows no `deep_freeze_peer: true`

### 2. Test Full ledger.json Generation
Re-test the full `gen ledger` command to verify ledger.json generation works correctly:
- Accounts with balances
- Trustlines (RippleState + DirectoryNodes)
- AMM pools (if configured)
- Proper ledger header and structure
- Validate output against xrpld requirements

### 3. Customizable Amendments
Add support for customizing which amendments are enabled in the generated ledger.json.

**Amendment Sources** (in priority order):
1. **xrpld source code**: Parse amendment definitions from rippled C++ source
   - Location: `src/libxrpl/protocol/Feature.cpp` (or similar)
   - Contains amendment names, IDs (SHA-512 hashes), and default states
2. **Running network**: Fetch enabled amendments via xrpld JSON-RPC API
   - `server_info` or `feature` commands on mainnet/testnet/devnet
   - Captures current network state (which amendments are actually enabled)
3. **User-provided file**: Load amendments from a local JSON/YAML file
   - Allows offline configuration and custom amendment sets
   - Useful for testing specific amendment combinations

**CLI Options** (proposed):
```bash
gen ledger --amendments-from-source /path/to/rippled/src  # Parse from xrpld source
gen ledger --amendments-from-network mainnet              # Fetch from network
gen ledger --amendments-from-file amendments.json         # Load from file
gen ledger --enable-amendment OwnerPaysFee               # Enable specific amendment
gen ledger --disable-amendment Clawback                  # Disable specific amendment
```

### 4. Default lsfDefaultRipple for All Accounts
Consider making `lsfDefaultRipple` the default flag for all generated accounts, with no-rippling as opt-out.

**Current behavior**: Only accounts used as issuers in AMM pools (`-a` flag) get `lsfDefaultRipple` automatically.

**Proposed behavior**: All accounts get `lsfDefaultRipple` by default. Add a CLI flag to opt-out:
```bash
gen ledger -n 10                          # All accounts have lsfDefaultRipple
gen ledger -n 10 --no-default-ripple      # Accounts have Flags=0 (opt-out)
gen ledger -n 10 --no-default-ripple 0,2  # Only accounts 0 and 2 opt-out
```

**Rationale**: Most test scenarios involve token issuance/trading. Having `lsfDefaultRipple` set by default reduces friction and unexpected `terNO_RIPPLE` errors.

### 5. Preset Account Seeds
Add the ability to provide preset seeds for deterministic account generation. This enables reproducible account addresses across runs.

**Input Sources**:
1. **Seed file (binary/hex)**: Raw 16-byte seeds (already supported in `bench_accounts.py`)
2. **Passphrase file**: One passphrase per line → derive seed via RFC-1751 or SHA-512
3. **Mnemonic file**: BIP-39 mnemonic phrases → derive seed

**CLI Options** (proposed):
```bash
gen ledger -n 10 --seeds-file seeds.bin                    # Load binary seeds
gen ledger -n 10 --seeds-file seeds.txt --seeds-text       # Load hex seeds (text)
gen ledger -n 10 --passphrases phrases.txt                 # Derive from passphrases
gen ledger -n 10 --mnemonics words.txt                     # Derive from BIP-39 mnemonics
gen ledger -n 10 --algo ed25519                            # Specify algorithm (ed25519/secp256k1)
```

**Requirements**:
- File must contain at least N seeds/passphrases for N accounts
- Algorithm must be specified or default to ed25519
- Support both binary (compact) and text (human-readable) seed formats
- Error if seed file has fewer entries than requested accounts

**Use Cases**:
- Reproducible test environments (same addresses every time)
- Pre-known account addresses for integration tests
- Migration from existing test fixtures with known keys

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
