# generate_ledger Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-01-21

## Active Technologies

- Python 3.12+ (currently 3.13) + xrpl-py (4.2.0+), typer/click (CLI), pydantic (validation), ruamel-yaml (config), httpx (networking), base58 (encoding) (001-xrpl-ledger-generator)

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
  - AMM pseudo-account (AccountRoot) with AMMID link
  - LP token currency derivation (0x03 + hash)
  - LP token trustline (RippleState) for liquidity providers
  - DirectoryNode consolidation for all AMM-related objects
  - Auction slot and vote slot initialization
  - Integration with LedgerConfig via AMMPoolConfig

### 🔴 Planned for v2.0
- **User Story 4 (P4)**: MPT (Multi-Purpose Tokens) support
- **User Story 6 (P6)**: Vault/Lending protocol support

### 🟡 In Progress
- Phase 9: Integration & Testing (tasks T058-T075)
- Phase 10: Polish & UX improvements (tasks T076-T085)
- Phase 11: Performance validation (tasks T086-T090)

## Recent Changes

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

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
