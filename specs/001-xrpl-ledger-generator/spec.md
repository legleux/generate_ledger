# Feature Specification: XRPL Custom Ledger Environment Generator

**Feature Branch**: `001-xrpl-ledger-generator`
**Created**: 2025-12-10
**Status**: Draft
**Input**: User description: "This package in incharge of preparing a custom XRPL environment capable of pre-generating a ledger such that sufficient state doesn't have to be established over time naturally but scenarios can be pre-generated. 3 Main modules the depend on each other such that some centralized context needs to be established in a certain order e.g. user input number variables, names, etc, can configure the ledger state, which might in turn affect the required rippled, validator config files which then might require docker file settings to correctly establish"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Configure Ledger State with Custom Accounts (Priority: P1)

A developer working on XRPL applications needs to set up a test environment with specific account balances, names, and configurations to test transaction scenarios without waiting for natural ledger progression.

**Why this priority**: This is the core value proposition - enabling rapid test environment setup with pre-defined state. Without this, developers must manually create and fund accounts over time, significantly slowing development and testing cycles.

**Independent Test**: Can be fully tested by providing account configuration parameters (count, names, balances) and verifying that the generated ledger contains the exact accounts with specified initial states.

**Acceptance Scenarios**:

1. **Given** a developer wants 10 test accounts with varying balances, **When** they specify account count and initial balance distribution, **Then** the system generates a ledger with exactly 10 accounts having the specified balances
2. **Given** a developer needs named accounts for testing (e.g., "alice", "bob", "carol"), **When** they provide account identifiers, **Then** the generated ledger includes accounts mapped to these identifiers with their credentials accessible
3. **Given** a developer wants to test with specific reserve settings, **When** they configure account_reserve and owner_reserve values, **Then** the generated ledger reflects these reserve requirements

---

### User Story 2 - Generate Validator Configuration Files (Priority: P2)

A developer needs validator nodes configured correctly to maintain the custom ledger state and consensus settings after initialization.

**Why this priority**: Without proper validator configuration, the custom ledger state would be lost or overridden after the initial setup. This is critical for maintaining the test environment but depends on having a ledger state defined first (P1).

**Independent Test**: Can be fully tested by providing ledger parameters (fee settings, reserves) and verifying that generated validator config files contain matching settings and prevent state changes from flag ledgers.

**Acceptance Scenarios**:

1. **Given** a custom ledger with specific fee settings (reference_fee, reserves), **When** validator configs are generated, **Then** all validator config files include the voting section with matching fee and reserve values
2. **Given** multiple validators are needed for consensus, **When** the developer specifies validator count, **Then** the system generates individual config files for each validator with unique identities and proper network settings
3. **Given** validators need to maintain custom state, **When** configs are generated, **Then** each validator is configured to recognize the custom genesis ledger

---

### User Story 3 - Deploy Docker-based Test Network (Priority: P3)

A developer wants to run the complete custom XRPL network in isolated containers to avoid conflicts with existing environments and enable easy teardown/recreation.

**Why this priority**: Docker deployment provides convenience and isolation but requires both ledger state (P1) and validator configs (P2) to be generated first. It's the final integration step that brings everything together.

**Independent Test**: Can be fully tested by running docker-compose with generated configurations and verifying that all validator containers start successfully, achieve consensus, and maintain the custom ledger state.

**Acceptance Scenarios**:

1. **Given** generated ledger state and validator configs, **When** docker-compose is executed, **Then** all validator containers start and form a functioning network
2. **Given** a running network, **When** querying ledger information, **Then** the custom initial state (accounts, balances, settings) is preserved
3. **Given** containers are running, **When** transactions are submitted, **Then** validators process them using the custom fee and reserve settings

---

### Edge Cases

- What happens when account balance configurations violate reserve requirements (balance < account_reserve)?
- How does the system handle validator count mismatches between config files and docker-compose?
- What happens if ledger state generation fails partway through (e.g., invalid parameters)?
- How does the system handle conflicts if a custom ledger already exists in the target directory?
- What happens when validator config parameters are inconsistent with ledger state parameters?

## Clarifications

### Session 2025-12-11

- Q: Which ledger object types will be supported in the initial release vs. future phases? → A: All ledger objects (Accounts, Trustlines, MPT, AMM, Vault/Lending) supported in initial release - full FR-010 scope
- Q: What specific ledger objects does "Lending Protocol primitives" refer to? → A: Vault objects (single-asset vaults specifically)
- Q: What are the maximum scalability limits the tool should support? → A: Medium scale (1000 accounts, 5000 trustlines, 10 validators)
- Q: What security approach should be used for storing account credentials? → A: Plain JSON files (acceptable for test networks, with security warnings in documentation)
- Q: What observability/logging strategy should be implemented? → A: Deferred to implementation phase

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept configuration parameters including account count, account identifiers, initial balances, fee settings (reference_fee), and reserve settings (account_reserve, owner_reserve)
- **FR-002**: System MUST generate a valid XRPL genesis ledger containing all specified accounts with their configured initial states
- **FR-003**: System MUST generate rippled configuration files for each validator that include voting sections with the custom fee and reserve settings
- **FR-004**: System MUST ensure validator configurations reference the custom genesis ledger to maintain state after initialization
- **FR-005**: System MUST generate docker-compose configuration that orchestrates all validator containers with proper networking and volume mounts
- **FR-006**: System MUST validate configuration parameters before generation to prevent invalid ledger states (e.g., balances meeting reserve requirements)
- **FR-007**: System MUST maintain dependency ordering where ledger state configuration informs validator config generation, which in turn informs docker deployment settings
- **FR-008**: System MUST provide access to generated account credentials (addresses, secrets) for testing purposes
- **FR-009**: System MUST generate configurations that enable validator consensus on the custom ledger
- **FR-010**: System MUST support pre-generation of ledger objects in the initial release, including: Accounts (AccountRoot), Trustlines (RippleState), MPT (Multi-Purpose Tokens via MPTokenIssuance and MPToken objects), AMM (Automated Market Maker via AMM objects and special AccountRoot), and Vault objects (single-asset vaults for lending/deposit functionality)
- **FR-011**: System MUST support generation of up to 1000 accounts, 5000 trustlines/ledger objects, and 10 validators (medium-scale test environments)
- **FR-012**: System MUST store generated account credentials (addresses and seeds) in plain JSON format with clear security warnings that these are for test networks only and should never be used in production environments

### Key Entities *(include if feature involves data)*

- **Account**: Represents an XRPL account with attributes including identifier/name, address, secret key, and initial XRP balance
- **Trustline**: Represents a trust relationship between two accounts for a specific currency, with balances and limits
- **MPToken**: Represents Multi-Purpose Token holdings, including issuance definition and individual holder balances
- **AMM**: Represents an Automated Market Maker pool with trading pair assets, liquidity provider tokens, and trading fee configuration
- **Vault**: Represents a single-asset vault for deposit/withdrawal functionality, with associated share tokens
- **Ledger State**: Represents the genesis ledger containing all pre-configured accounts, trustlines, tokens, AMMs, vaults, balances, and ledger settings (fees, reserves)
- **Validator Configuration**: Represents rippled configuration for a single validator node, including network settings, voting parameters, and genesis ledger reference
- **Network Configuration**: Represents the complete test network deployment specification including all validators, container settings, and network topology

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Developers can generate a complete custom XRPL test environment in under 5 minutes from configuration to running network
- **SC-002**: Generated ledger state accurately reflects 100% of specified account configurations (count, balances, identifiers)
- **SC-003**: Validator network achieves consensus and processes transactions within 5 seconds of startup
- **SC-004**: Custom fee and reserve settings persist across ledger closes and validator restarts
- **SC-005**: Developers can recreate identical test environments by reusing the same configuration parameters
- **SC-006**: Zero manual configuration file editing required after generation - system produces deployment-ready artifacts
