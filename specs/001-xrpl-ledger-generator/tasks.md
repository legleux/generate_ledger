# Tasks: XRPL Custom Ledger Environment Generator

**Input**: Design documents from `/specs/001-xrpl-ledger-generator/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Not explicitly requested in specification - integration tests will verify functionality

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

**Current Status**: Core functionality (accounts, trustlines, validators, docker) and AMM are implemented. Amendment system overhauled with profile-based loading. Test suite expanded to 253 tests. Remaining work: MPT (US4), Vault (US6), and finalization.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure) ✅ COMPLETE

**Purpose**: Project initialization and basic structure

**Status**: Already implemented - Python project with uv, typer CLI, pydantic models

- [x] T001 Create project structure per implementation plan
- [x] T002 Initialize Python project with xrpl-py, typer, pydantic dependencies
- [x] T003 [P] Configure linting (ruff) and formatting tools

---

## Phase 2: Foundational (Blocking Prerequisites) ✅ COMPLETE

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

**Status**: Core infrastructure is in place

- [x] T004 Implement account generation in src/generate_ledger/accounts.py
- [x] T005 [P] Implement ledger indices calculation in src/generate_ledger/indices.py
- [x] T006 [P] Create amendment list management in src/generate_ledger/amendments.py
- [x] T007 Implement ledger builder in src/generate_ledger/ledger_builder.py
- [x] T008 Implement validator key generation in src/generate_ledger/rippled_cfg.py
- [x] T009 Create CLI framework in src/generate_ledger/cli/main.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Configure Ledger State with Custom Accounts (Priority: P1) ✅ COMPLETE

**Goal**: Enable developers to set up test environment with specific account balances, names, and configurations

**Independent Test**: Provide account configuration parameters and verify generated ledger contains exact accounts with specified initial states

**Status**: ✅ COMPLETE - Accounts and trustlines are fully implemented

### Implementation for User Story 1 (COMPLETE)

- [x] T010 [P] [US1] Create Account model in src/generate_ledger/accounts.py
- [x] T011 [P] [US1] Create Trustline model in src/generate_ledger/trustlines.py
- [x] T012 [US1] Implement account generation service in src/generate_ledger/ledger_builder.py
- [x] T013 [US1] Implement trustline generation with RippleState + DirectoryNode objects in src/generate_ledger/trustlines.py
- [x] T014 [US1] Add account credentials export in src/generate_ledger/ledger_builder.py
- [x] T015 [US1] Implement reserve validation in src/generate_ledger/ledger_builder.py
- [x] T016 [US1] Add CLI command `gen ledger` in src/generate_ledger/cli/ledger.py
- [x] T017 [US1] Integrate trustlines into ledger assembly in src/generate_ledger/ledger_builder.py

**Checkpoint**: ✅ User Story 1 is fully functional - accounts and trustlines can be generated with custom configurations

---

## Phase 4: User Story 2 - Generate Validator Configuration Files (Priority: P2) ✅ COMPLETE

**Goal**: Enable developers to configure validator nodes correctly to maintain custom ledger state

**Independent Test**: Provide ledger parameters and verify validator config files contain matching settings

**Status**: ✅ COMPLETE - Validator configuration generation is fully implemented

### Implementation for User Story 2 (COMPLETE)

- [x] T018 [P] [US2] Create ValidatorIdentity model in src/generate_ledger/rippled_cfg.py
- [x] T019 [P] [US2] Implement validator key generation in src/generate_ledger/rippled_cfg.py
- [x] T020 [US2] Create rippled.cfg template generation in src/generate_ledger/rippled_cfg.py
- [x] T021 [US2] Implement UNL (Unique Node List) generation in src/generate_ledger/rippled_cfg.py
- [x] T022 [US2] Add voting section with fee/reserve settings in src/generate_ledger/rippled_cfg.py
- [x] T023 [US2] Implement fixed peer connections (ips_fixed) in src/generate_ledger/rippled_cfg.py
- [x] T024 [US2] Add CLI command `gen validators` in src/generate_ledger/cli/rippled_cfg.py
- [x] T025 [US2] Ensure validator configs reference custom genesis ledger in src/generate_ledger/rippled_cfg.py

**Checkpoint**: ✅ User Story 2 is fully functional - validator configurations maintain custom ledger state

---

## Phase 5: User Story 3 - Deploy Docker-based Test Network (Priority: P3) ✅ COMPLETE

**Goal**: Enable developers to run complete custom XRPL network in isolated containers

**Independent Test**: Run docker-compose and verify all validators start, achieve consensus, and maintain custom ledger state

**Status**: ✅ COMPLETE - Docker compose generation is fully implemented

### Implementation for User Story 3 (COMPLETE)

- [x] T026 [P] [US3] Create ContainerConfig model in src/generate_ledger/compose.py
- [x] T027 [P] [US3] Implement docker-compose.yml generation in src/generate_ledger/compose.py
- [x] T028 [US3] Add network configuration with bridge networking in src/generate_ledger/compose.py
- [x] T029 [US3] Implement validator service definitions in src/generate_ledger/compose.py
- [x] T030 [US3] Add volume mount configuration in src/generate_ledger/compose.py
- [x] T031 [US3] Implement dependency ordering (val0 bootstrap) in src/generate_ledger/compose.py
- [x] T032 [US3] Add CLI command `gen compose` in src/generate_ledger/cli/compose.py
- [x] T033 [US3] Add CLI command `gen auto` for complete environment in src/generate_ledger/cli/auto.py

**Checkpoint**: ✅ User Stories 1, 2, and 3 are all complete - full test network deployment works

---

## Phase 6: MPT Support (Multi-Purpose Tokens) - FR-010 Extension (Priority: P4)

**Goal**: Support pre-generation of Multi-Purpose Token (MPT) ledger objects

**Independent Test**: Generate ledger with MPT issuance and holder balances, verify MPTokenIssuance and MPToken objects are created correctly

**Status**: 🔴 NOT STARTED

### Implementation for MPT Support

- [ ] T034 [P] [US4] Research MPT ledger object structure in specs/001-xrpl-ledger-generator/research.md
- [ ] T035 [P] [US4] Create MPTConfig model in src/generate_ledger/models/mpt.py
- [ ] T036 [US4] Implement MPTokenIssuance object generation in src/generate_ledger/mpt.py
- [ ] T037 [US4] Implement MPToken holder object generation in src/generate_ledger/mpt.py
- [ ] T038 [US4] Calculate MPT ledger indices in src/generate_ledger/indices.py
- [ ] T039 [US4] Integrate MPT objects into ledger assembly in src/generate_ledger/ledger_builder.py
- [ ] T040 [US4] Add CLI options for MPT generation to `gen ledger` in src/generate_ledger/cli/ledger.py
- [ ] T041 [US4] Update OwnerCount calculation for MPT holders in src/generate_ledger/ledger_builder.py

**Checkpoint**: MPT support complete - ledger can include Multi-Purpose Tokens

---

## Phase 7: AMM Support (Automated Market Maker) - FR-010 Extension (Priority: P5)

**Goal**: Support pre-generation of AMM pool ledger objects

**Independent Test**: Generate ledger with AMM pools, verify AMM objects and special AccountRoot entries are created correctly

**Status**: ✅ COMPLETE

**Implementation**: Genesis-based approach works — no transaction initialization needed. Full AMM pool generation in src/generate_ledger/amm.py (472 lines), 32 tests, CLI support (`--amm-pool/-a`).

### Implementation for AMM Support (COMPLETE)

- [x] T042 [P] [US5] Research AMM initialization requirements in specs/001-xrpl-ledger-generator/research.md
- [x] T043 [P] [US5] Create AMMConfig model in src/generate_ledger/models/amm.py
- [x] T044 [US5] Implement AMM object generation in src/generate_ledger/amm.py
- [x] T045 [US5] Create AMM special AccountRoot (if required) in src/generate_ledger/amm.py
- [x] T046 [US5] Calculate AMM ledger indices in src/generate_ledger/indices.py
- [x] T047 [US5] Integrate AMM objects into ledger assembly in src/generate_ledger/ledger_builder.py
- [x] T048 [US5] Add CLI options for AMM generation to `gen ledger` in src/generate_ledger/cli/ledger.py
- [x] T049 [US5] Handle LP token accounting in AMM pools in src/generate_ledger/amm.py

**Checkpoint**: ✅ AMM support complete - ledger can include automated market maker pools with proper indices, LP token accounting, and pseudo-account derivation

---

## Phase 8: Vault/Lending Support (Single-Asset Vaults) - FR-010 Extension (Priority: P6)

**Goal**: Support pre-generation of Vault ledger objects for deposit/lending functionality

**Independent Test**: Generate ledger with vault objects, verify vault entries and share tokens are created correctly

**Status**: 🔴 NOT STARTED

### Implementation for Vault Support

- [ ] T050 [P] [US6] Research Vault ledger object structure in specs/001-xrpl-ledger-generator/research.md
- [ ] T051 [P] [US6] Create VaultConfig model in src/generate_ledger/models/vault.py
- [ ] T052 [US6] Implement Vault object generation in src/generate_ledger/vault.py
- [ ] T053 [US6] Implement share token accounting for vaults in src/generate_ledger/vault.py
- [ ] T054 [US6] Calculate Vault ledger indices in src/generate_ledger/indices.py
- [ ] T055 [US6] Integrate Vault objects into ledger assembly in src/generate_ledger/ledger_builder.py
- [ ] T056 [US6] Add CLI options for Vault generation to `gen ledger` in src/generate_ledger/cli/ledger.py
- [ ] T057 [US6] Update OwnerCount calculation for vault owners in src/generate_ledger/ledger_builder.py

**Checkpoint**: Vault support complete - ledger can include lending/deposit vaults

---

## Phase 9: Integration & Testing

**Purpose**: End-to-end validation and testing of all features

**Status**: 🟡 PARTIAL - Core features work, advanced features need testing

- [ ] T058 [P] Test complete environment generation with `gen auto` command
- [ ] T059 [P] Test ledger generation with accounts only
- [ ] T060 [P] Test ledger generation with accounts + trustlines
- [ ] T061 Test validator network consensus with generated configs
- [ ] T062 Test Docker deployment with docker-compose
- [ ] T063 [P] Test reserve validation (balances meeting requirements)
- [ ] T064 [P] Test total coins validation (sum equals 100B XRP)
- [ ] T065 Test cross-command consistency (validators match compose)
- [ ] T066 [P] Test MPT generation end-to-end (once implemented)
- [ ] T067 [P] Test AMM generation end-to-end (once implemented)
- [ ] T068 [P] Test Vault generation end-to-end (once implemented)
- [ ] T069 Test medium-scale generation (1000 accounts, 5000 trustlines, 10 validators)
- [ ] T070 Validate quickstart.md instructions work end-to-end
- [ ] T071 [P] Test edge case: balance/reserve requirement violations in src/generate_ledger/ledger_builder.py
- [ ] T072 [P] Test edge case: validator count mismatch between gen validators and gen compose
- [ ] T073 [P] Test edge case: ledger generation partial failure with rollback
- [ ] T074 [P] Test edge case: file conflict handling when ledger already exists
- [ ] T075 [P] Test edge case: parameter inconsistency between ledger and validator configs

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

**Status**: 🟡 PARTIAL

- [ ] T076 [P] Add comprehensive error messages for validation failures
- [ ] T077 [P] Implement JSON output mode (--json flag) for programmatic use
- [ ] T078 [P] Add progress indicators for long-running operations
- [ ] T079 Add security warnings to account credential output files with text: "WARNING: These credentials are for TEST NETWORKS ONLY. Never use in production."
- [ ] T080 [P] Create example configurations in examples/ directory
- [ ] T081 [P] Add verbose logging mode (--verbose flag)
- [ ] T082 Performance optimization for large ledger generation (1000+ accounts)
- [ ] T083 [P] Update README.md with usage examples
- [ ] T084 Code cleanup and refactoring for consistency

---

## Phase 11: Performance Validation

**Purpose**: Validate success criteria performance requirements

**Status**: 🔴 NOT STARTED

- [ ] T085 [P] Measure and validate SC-001: Complete environment generation in under 5 minutes
- [ ] T086 [P] Performance benchmark: 100 accounts generation time
- [ ] T087 [P] Performance benchmark: 500 accounts + 1000 trustlines generation time
- [ ] T088 [P] Performance benchmark: 1000 accounts + 5000 trustlines + 10 validators (FR-011 max scale)
- [ ] T089 Add credentials export validation test for FR-008 (verify accounts.json format and accessibility)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: ✅ COMPLETE
- **Foundational (Phase 2)**: ✅ COMPLETE - Blocks all user stories
- **User Story 1 (Phase 3)**: ✅ COMPLETE - Accounts and Trustlines
- **User Story 2 (Phase 4)**: ✅ COMPLETE - Validator Configs
- **User Story 3 (Phase 5)**: ✅ COMPLETE - Docker Deployment
- **User Story 4 (Phase 6)**: 🔴 NOT STARTED - MPT Support (depends on Phase 2)
- **User Story 5 (Phase 7)**: ✅ COMPLETE - AMM Support
- **User Story 6 (Phase 8)**: 🔴 NOT STARTED - Vault Support (depends on Phase 2)
- **Integration (Phase 9)**: 🟡 PARTIAL - Ongoing testing as features complete
- **Polish (Phase 10)**: 🟡 PARTIAL - Ongoing improvements

### User Story Dependencies

- **User Story 1 (P1)**: ✅ COMPLETE - No dependencies on other stories
- **User Story 2 (P2)**: ✅ COMPLETE - Integrates with US1 (ledger settings)
- **User Story 3 (P3)**: ✅ COMPLETE - Depends on US1 + US2 (needs ledger + configs)
- **User Story 4 (P4)**: 🔴 MPT - Independent of US1-3, parallel implementable
- **User Story 5 (P5)**: ✅ AMM - Complete, genesis-based approach works
- **User Story 6 (P6)**: 🔴 Vault - Independent of US1-5, parallel implementable

### Parallel Opportunities

- ✅ US1, US2, US3 are complete and work together
- ✅ US5 (AMM) is complete. 🔴 US4 (MPT) and US6 (Vault) can be implemented in parallel (different files)
- Testing tasks (T058-T070) can run in parallel once features are implemented
- Polish tasks (T071-T080) can run in parallel

---

## Implementation Strategy

### Current Status: MVP + AMM Complete ✅

**Completed**:
1. ✅ Phase 1: Setup
2. ✅ Phase 2: Foundational
3. ✅ Phase 3: User Story 1 (Accounts + Trustlines)
4. ✅ Phase 4: User Story 2 (Validator Configs)
5. ✅ Phase 5: User Story 3 (Docker Deployment)
6. ✅ Phase 7: User Story 5 (AMM Support)

**Additional completions** (not task-tracked):
- ✅ Amendment system overhaul: profile-based loading, features.macro parser, per-amendment overrides
- ✅ Test suite: 46 → 253 tests across 18 test files
- ✅ Stable vs Develop separation: `develop/` package with object registry

**MVP + AMM Functionality**: Developers can generate complete custom XRPL test environments with accounts, trustlines, AMM pools, validators, and Docker deployment.

### Next Steps: Remaining Advanced Features

**Option 1 - Complete FR-010 (Remaining Ledger Objects)**:
1. Implement Phase 6: MPT Support
2. Implement Phase 8: Vault Support
3. Complete Phase 9: Integration & Testing
4. Finalize Phase 10: Polish

**Option 2 - Production Readiness**:
1. Focus on Phase 9: Integration & Testing (validate existing features including AMM)
2. Complete Phase 10: Polish (documentation, error handling, UX)
3. Defer remaining advanced ledger objects (MPT, Vault) to future releases

### Parallel Team Strategy

With multiple developers:

1. ✅ Core team has completed MVP (US1-3) + AMM (US5)
2. 🔴 Now parallelize remaining features:
   - Developer A: Phase 6 (MPT Support)
   - Developer B: Phase 8 (Vault Support)
   - Developer C: Phase 9 & 10 (Testing & Polish)

---

## Notes

- ✅ = Complete, 🟡 = Partial/In Progress, 🔴 = Not Started
- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Core MVP (US1-3) and AMM (US5) are complete and functional
- Remaining advanced features (MPT, Vault) are independent and can be implemented in parallel
- Amendment system overhauled with profile-based loading (release/develop/custom)
- Test suite expanded from 46 → 253 tests
- Focus next on either remaining features OR production hardening
- **Total Tasks**: 89 (41 complete, 48 pending)
- **Edge Case Coverage**: T071-T075 address all spec.md edge cases
- **Performance Validation**: T085-T089 validate success criteria timing requirements
- **CLAUDE.md Updates**: Should be done continuously as part of completing phases/milestones, not as a separate task
