# Implementation Plan: XRPL Custom Ledger Environment Generator

**Branch**: `001-xrpl-ledger-generator` | **Date**: 2025-12-10 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-xrpl-ledger-generator/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

This feature enables developers to generate complete custom XRPL test environments with pre-configured ledger state (accounts, trustlines, MPT, AMM, lending protocol primitives), validator configurations, and Docker deployment artifacts. The system generates deployment-ready configurations in under 5 minutes, eliminating the need for manual environment setup and natural ledger progression time.

## Technical Context

**Language/Version**: Python 3.12+ (currently 3.13)
**Primary Dependencies**: xrpl-py (4.2.0+), typer/click (CLI), pydantic (validation), ruamel-yaml (config), httpx (networking), base58 (encoding)
**Storage**: File-based (JSON ledger files, INI/YAML config files, docker-compose YAML)
**Testing**: pytest (8.4.1+), integration tests for rippled interaction
**Target Platform**: Linux/macOS development environments, Docker containers for validators
**Project Type**: Single CLI tool with library modules
**Performance Goals**: Complete environment generation in <5 minutes, handle 1000+ accounts per ledger
**Constraints**: Must generate valid XRPL ledger format, validator configs must achieve consensus, Docker network must be isolated
**Scale/Scope**: Support 5-10 validators per network, up to 10,000 accounts, multiple ledger object types (Accounts, Trustlines, MPT, AMM, Lending primitives)

### Key Technical Decisions Requiring Research

1. **XRPL Genesis Ledger Format**: ✅ RESOLVED - See research.md. Structure implemented in src/generate_ledger/ledger_builder.py with AccountRoot, RippleState, FeeSettings, and Amendments objects.
2. **MPT Creation**: 🔴 DEFERRED to v2.0 - Requires additional research on MPTokenIssuance and MPToken ledger object specifications.
3. **AMM Initialization**: 🔴 DEFERRED to v2.0 - Research indicates AMM pools may require transaction-based initialization post-genesis. See tasks.md T042.
4. **Lending Protocol Primitives**: 🔴 DEFERRED to v2.0 - Vault object specifications require further research. See tasks.md T050.
5. **Validator Identity Generation**: ✅ RESOLVED - Implemented using xrpl-py Wallet generation with secp256k1. See src/generate_ledger/rippled_cfg.py.
6. **Docker Network Topology**: ✅ RESOLVED - Bridge networking with fixed peer connections (ips_fixed). Bootstrap validator (val0) dependency pattern. See src/generate_ledger/compose.py.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Note**: Project constitution template is currently empty/not ratified. Proceeding with standard software engineering best practices:

- **Modularity**: ✅ Design follows separation of concerns (ledger generation, config generation, Docker orchestration as distinct modules)
- **Testability**: ✅ Each module can be unit tested independently; integration tests will verify end-to-end functionality
- **Documentation**: ✅ Will provide quickstart guide, API documentation, and usage examples
- **Error Handling**: ✅ Will validate all inputs before generation to prevent invalid states
- **Backward Compatibility**: ✅ Initial version, no compatibility concerns

**Status**: PASSED - No constitution violations identified

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/generate_ledger/
├── models/                    # Data models (ledger objects, configurations)
│   ├── ledger.py             # Ledger state models
│   ├── namespace.py          # Account namespace models
│   └── ripplestate.py        # Trustline/RippleState models
├── services/                  # Business logic services
│   ├── ledger_service.py     # Ledger generation service
│   ├── config_service.py     # Validator config generation
│   └── compose_service.py    # Docker compose generation
├── cli/                       # CLI commands
│   ├── main.py               # Main CLI entry point
│   ├── ledger.py             # Ledger generation commands
│   ├── rippled_cfg.py        # Config generation commands
│   └── compose.py            # Docker compose commands
├── commands/                  # Command implementations
│   ├── ledger_writer.py      # Ledger file writing
│   ├── config.py             # Config file generation
│   └── compose_writer.py     # Docker compose writing
├── utils/                     # Utility functions
│   ├── config.py             # Configuration helpers
│   ├── paths.py              # Path utilities
│   └── merging.py            # Data merging utilities
├── topo/                      # Network topology (if needed)
│   └── topology_to_ripple_cfg.py
├── accounts.py                # Account generation
├── trustlines.py              # Trustline generation
├── amendments.py              # XRPL amendments
└── config.py                  # Global configuration

tests/
├── cli/                       # CLI tests
├── lib/                       # Library/unit tests
└── data/                      # Test fixtures
```

**Structure Decision**: Using single project structure (Option 1). The existing codebase follows a modular CLI tool pattern with clear separation between models, services, CLI commands, and utilities. This structure supports the three main modules described in the spec: ledger state configuration, validator config generation, and Docker deployment configuration.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
