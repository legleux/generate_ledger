# generate_ledger Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-02-23

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
├── crypto.py            # XRPL crypto primitives (sha512_half, ripesha)
├── accounts.py          # Account generation
├── trustlines.py        # Trustline generation (✅ COMPLETE - commit 955aae3)
├── amm.py               # AMM pool generation (✅ COMPLETE - 2026-01-21)
├── amendments.py        # XRPL amendments (✅ overhauled: profiles, features.macro parser, hash)
├── indices.py           # Ledger index calculations (includes AMM index, account, LP token)
├── ledger_builder.py    # Ledger assembly (supports trustlines + AMM + extra_objects)
├── ledger.py            # gen_ledger_state() pipeline, LedgerConfig (profile-based amendments)
├── rippled_cfg.py       # Validator config generation
├── compose.py           # Docker compose generation
├── data/
│   ├── amendment_list_dev_20250907.json   # Legacy devnet amendments
│   └── amendments_release.json            # Curated release amendments
└── develop/             # Pre-release objects (absent on main branch)
    ├── __init__.py      # Object registry (get_develop_builders)
    ├── mpt.py           # MPToken placeholder
    └── vault.py         # Vault placeholder

tests/
├── cli/                 # CLI tests (parsers, smoke, ledger command)
├── lib/                 # Library/unit tests (indices, accounts, trustlines, amm, ledger_builder, amendments, amendment_parser, develop_registry)
├── integration/         # Integration tests (gen_ledger_state pipeline)
└── data/                # Test fixtures (including features_test.macro)

scripts/
├── bench_accounts.py    # Account + trustline benchmark (parallel strategies, native crypto)
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

# Generate ledger with amendment profiles
gen ledger -n 10 --amendment-profile release                                    # Use curated release amendments
gen ledger -n 10 --amendment-profile develop --amendment-source /path/to/features.macro  # Parse from rippled source
gen ledger -n 10 --amendment-profile custom --amendment-source amendments.json   # Custom JSON file
gen ledger -n 10 --enable-amendment SomeFeature --disable-amendment Clawback     # Per-amendment overrides

# Generate validators
gen validators --count 5 --output-dir ./volumes

# Generate docker compose
gen compose --validators 5 --output ./docker-compose.yml

# Benchmark account + trustline generation (see scripts/README.md for details)
uv run scripts/bench_accounts.py --info                                    # Check available backends
uv run scripts/bench_accounts.py -n 10000 --algo ed25519 --mode mp         # Benchmark accounts
uv run scripts/bench_accounts.py -n 1000 --trustlines --mode mp            # Benchmark accounts + trustlines
uv run scripts/bench_accounts.py -n 100 --trustlines --topology mesh       # Benchmark mesh topology

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

### ✅ Test Suite Overhaul Complete
- **Phase 9 (partial)**: Core logic test coverage added
  - 148 new tests across 8 test files (46 → 193 total)
  - Index calculations: 35 tests with rippled-verified test vectors
  - AMM module: 28 tests including critical flag regression tests
  - Trustlines: 18 tests covering object generation and dedup
  - Ledger assembly: 15 tests including directory consolidation
  - Full pipeline integration: 13 tests through gen_ledger_state()
  - CLI ledger command: 7 smoke tests
  - Accounts + Amendments: 19 tests combined

### ✅ Stable vs Develop Separation Complete
- Amendment system overhaul: `amendment_hash()`, `parse_features_macro()`, `AmendmentProfile` enum
- Profile-based loading: `release` (curated JSON), `develop` (features.macro parser), `custom` (user JSON)
- Per-amendment `--enable-amendment` / `--disable-amendment` overrides
- `develop/` package with object registry and graceful `ImportError` handling
- `extra_objects` parameter in `assemble_ledger_json()` for develop builders
- 42 new tests (193 → 235, then 235 → 253 with retired/obsolete amendment tests)

### 🟡 Remaining Work
- Phase 6: MPT Support (tasks T034-T041) — 🔴 NOT STARTED
- Phase 8: Vault Support (tasks T050-T057) — 🔴 NOT STARTED
- Phase 9: Integration & Testing — remaining tasks (T058-T075), live rippled validation
- Phase 10: Polish & UX improvements (tasks T076-T085)
- Phase 11: Performance validation (tasks T086-T090)

## Recent Changes

- 2026-02-23: Spec files synchronized with implementation reality
  - `tasks.md`: Marked Phase 7 (AMM) T042-T049 as complete, updated counts (33→41 complete, 56→48 pending)
  - `spec.md`: Updated status line, added Session 2026-02-23 entry, marked FR-010 AMM as ✅ COMPLETE
  - `plan.md`: Resolved AMM technical decision (was 🔴 DEFERRED, now ✅ RESOLVED)
  - All three spec files now consistent with CLAUDE.md as source of truth

- 2026-02-23: Added retired + obsolete amendments to `amendments_release.json`
  - 15 retired amendments (MultiSign, TrustSetAuth, FeeEscalation, PayChan, CryptoConditions, TickSize, fix1368, Escrow, fix1373, EnforceInvariants, SortedDirectories, fix1201, fix1512, fix1523, fix1528) — `enabled: true, retired: true`
  - 4 obsolete amendments (fixNFTokenNegOffer, fixNFTokenDirV1, NonFungibleTokensV1, CryptoConditionsSuite) — `enabled: false, obsolete: true`
  - Total amendments: 73 → 92
  - Updated `test_all_enabled` to handle obsolete (enabled=false) entries
  - Added `test_retired_count`, `test_obsolete_count`, `test_total_count` tests

- 2026-02-23: Stable vs Develop ledger object separation
  - Amendment system overhaul in `amendments.py`: `amendment_hash()`, `parse_features_macro()`, `AmendmentProfile`, `get_amendments_for_profile()`
  - New CLI flags: `--amendment-profile`, `--amendment-source`, `--enable-amendment`, `--disable-amendment`
  - New `develop/` package: object registry (`get_develop_builders()`), MPT + Vault stubs
  - `ledger_builder.py`: `extra_objects` parameter for develop builders
  - `ledger.py`: profile-based amendment loading, develop builder discovery with graceful ImportError
  - New `data/amendments_release.json`: curated release amendments (73 amendments, later expanded to 92)
  - 42 new tests in `test_amendment_parser.py` (36) and `test_develop_registry.py` (6+1)
  - Test fixture: `tests/data/features_test.macro`
  - Branch strategy: `main` = release (no develop/), `develop` = develop (has develop/)

- 2026-02-23: Test suite overhaul — 148 new tests (46 → 193 total, all passing)
  - New files: `test_indices.py`, `test_accounts.py`, `test_trustlines.py`, `test_amm.py`, `test_ledger_builder.py`, `test_amendments.py`, `test_gen_ledger_state.py`, `test_cli_ledger.py`
  - Regression tests for both 2026-01-28 AMM bug fixes (lsfAMMNode flag, account derivation)
  - Test vectors verified against running rippled node (genesis/alice/bob indices, amendments index)
  - Shared fixtures in `tests/conftest.py` (deterministic accounts, known indices)

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

- 2026-01-27: Trustline benchmarking (`scripts/bench_accounts.py`)
  - Trustline object generation benchmark (RippleState + 2 DirectoryNodes)
  - Self-contained index calculations (no generate_ledger dependency for benchmarks)
  - Topology strategies: star, ring, mesh, random
  - CLI: `--trustlines`, `--topology`, `--currencies`

- 2026-01-27: Account generation benchmark script (`scripts/bench_accounts.py`)
  - Parallel execution modes: sequential, multiprocessing, threading, hybrid
  - Native crypto backends: PyNaCl (ed25519 ~50k/sec), coincurve/fastecdsa (secp256k1 ~15k/sec)
  - Python 3.13t (free-threaded/no-GIL) support for true thread parallelism
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

### Option A - Production Hardening (Recommended)
Focus on validating and polishing existing MVP + AMM functionality:
1. Execute Phase 9: Integration & Testing (T058-T075)
   - Test complete environment generation (including AMM)
   - Test accounts + trustlines + AMM generation
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

### Option B - Remaining Advanced Features (v2.0)
Implement remaining ledger object types:
1. Phase 6: MPT Support (tasks T034-T041)
   - Research MPT ledger object structure
   - Implement MPTokenIssuance and MPToken generation
   - Add CLI options for MPT
2. Phase 8: Vault Support (tasks T050-T057)
   - Research Vault ledger object structure
   - Implement single-asset vault generation
   - Add share token accounting
3. Then execute Phases 9-11 for full validation

### Key Files to Reference
- Spec: `specs/001-xrpl-ledger-generator/spec.md`
- Tasks: `specs/001-xrpl-ledger-generator/tasks.md`
- Plan: `specs/001-xrpl-ledger-generator/plan.md`
- Data Model: `specs/001-xrpl-ledger-generator/data-model.md`
- CLI Contract: `specs/001-xrpl-ledger-generator/contracts/cli-interface.md`

## Next TODOs

### 0. VERIFY: What happens when amendment hashes are omitted from genesis ledger?
**STATUS: UNTESTED — DO NOT SKIP THIS**

We added retired + obsolete amendments to `amendments_release.json` based on the
assumption that rippled needs them in the genesis ledger. This has NOT been verified.

**Test procedure:**
1. Generate a ledger.json WITHOUT the 15 retired amendments
2. Start rippled with that ledger
3. Does it boot? Does it crash? Does it log warnings?
4. Try submitting transactions that use retired features (MultiSign, Escrow, PayChan)
5. Document the actual behavior

This determines whether retired amendments are truly critical or just nice-to-have.

### 0B. PRIORITY: Live network validation of enabled amendments

**Unit tests only prove the JSON has correct hashes. We need to prove rippled actually enables the features.**

When rippled knows about an amendment but it is NOT enabled in the genesis ledger, submitting a transaction that uses that feature returns a clear error (e.g. `temDISABLED` or `notEnabled`). This is the definitive test.

**Approach:** docker-compose project using rippled images with develop features compiled in, bootstrapped with our generated `ledger.json`.

**Test procedure:**
1. Generate `ledger.json` with develop profile (all features enabled)
2. `docker-compose up` a single-validator network using a rippled image that has the develop features compiled in
3. Submit transactions that exercise feature-gated functionality:
   - AMM: `AMMCreate`, `AMMDeposit` (two-asset) — proves AMM amendment is active
   - Clawback: `Clawback` tx — proves Clawback amendment is active
   - MPT (when implemented): `MPTokenIssuanceCreate` — proves MPTokensV1 is active
   - DID: `DIDSet` — proves DID amendment is active
4. Verify each tx succeeds (not `temDISABLED` / `notEnabled`)
5. **Negative test:** Generate a ledger with a known feature disabled (e.g. `--disable-amendment AMM`), restart rippled, submit `AMMCreate` — expect rejection

This is the only way to confirm end-to-end that our amendment hashes are correct and rippled treats them as enabled.

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

### ~~3. Customizable Amendments~~ ✅ COMPLETE
Implemented in `amendments.py` with profile-based loading:
- `--amendment-profile release|develop|custom`
- `--amendment-source PATH` (features.macro or custom JSON)
- `--enable-amendment NAME` / `--disable-amendment NAME` (repeatable overrides)
- `parse_features_macro()` parses XRPL_FEATURE/XRPL_FIX/XRPL_RETIRE_* macros
- `amendment_hash()` computes SHA512Half(name) matching rippled's Feature.cpp

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
Add the ability to provide preset seeds for deterministic account generation. This enables reproducible account addresses across runs. Use xrpl-py's seed/keypair APIs upstream rather than custom I/O.

**CLI Options** (proposed):
```bash
gen ledger -n 10 --seeds-file seeds.json                   # Load seeds (xrpl-py format)
gen ledger -n 10 --passphrases phrases.txt                 # Derive from passphrases
gen ledger -n 10 --algo ed25519                            # Specify algorithm (ed25519/secp256k1)
```

**Requirements**:
- File must contain at least N seeds for N accounts
- Algorithm must be specified or default to ed25519
- Error if seed file has fewer entries than requested accounts

**Use Cases**:
- Reproducible test environments (same addresses every time)
- Pre-known account addresses for integration tests
- Migration from existing test fixtures with known keys

<!-- MANUAL ADDITIONS START -->

### 6. Consider renaming package to "ledgen"
Short, memorable, and sounds like "legend." Would involve renaming `src/generate_ledger/` → `src/ledgen/`, updating pyproject.toml, imports, tests, CLI entry point, etc.

### 7. Pre-created Offers in genesis ledger
Generate `Offer` ledger objects so the order book is already populated at genesis.
- CLI: `--offer "buy_account:sell_account:TakerPays:TakerGets:rate"` or similar
- Objects needed: `Offer` entries + `DirectoryNode` for offer book directories
- Offer book directory index: `SHA512Half(0x0042 + TakerPaysCurrency + TakerPaysIssuer + TakerGetsCurrency + TakerGetsIssuer)`
- Each `Offer` also needs an owner directory entry and `OwnerCount` increment
- Enables testing DEX functionality (OfferCreate crossing, Payment with auto-bridging) immediately on boot

### 8. Sample genesis ledgers
Maintain ready-to-use sample ledgers in `samples/`:
- `samples/simple-10/` — 10 accounts, no trustlines or AMM (basic testing)
- `samples/rich-100/` — 100 accounts, 5 gateways (USD/EUR/GBP/JPY/BTC), 25 trustlines, 5 AMM pools
- Future: add offers on the books once TODO #7 is implemented
- Future: add a "kitchen sink" sample with every object type (offers, MPT, vaults)
- Regenerate samples when the ledger format changes

<!-- MANUAL ADDITIONS END -->
