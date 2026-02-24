# CLI Interface Contract

**Feature**: 001-xrpl-ledger-generator
**Date**: 2025-12-10
**Type**: Command-Line Interface

## Overview

This document specifies the command-line interface (CLI) for the XRPL Custom Ledger Environment Generator. The CLI provides commands for generating ledger state, validator configurations, and Docker deployment artifacts.

## Global CLI Entry Point

**Command**: `gen`
**Description**: Main CLI entry point for the ledger generator

### Usage
```bash
gen [COMMAND] [OPTIONS]
```

### Global Options
- `--help`: Show help message
- `--version`: Show version information
- `--verbose, -v`: Enable verbose output
- `--config FILE`: Load configuration from file (default: `.env`)

## Commands

### 1. Generate Complete Environment

**Command**: `gen auto`

**Purpose**: Generate complete test environment (ledger + validators + docker-compose) in one command

**Usage**:
```bash
gen auto [OPTIONS]
```

**Options**:
- `--accounts INTEGER`: Number of accounts to generate (default: 10)
- `--validators INTEGER`: Number of validators (default: 5, min: 4)
- `--output-dir PATH`: Output directory (default: `./testnet`)
- `--network-name TEXT`: Docker network name (default: `xrpl_net`)
- `--reference-fee INTEGER`: Base fee in drops (default: 10)
- `--account-reserve INTEGER`: Account reserve in drops (default: 2000000)
- `--owner-reserve INTEGER`: Owner reserve in drops (default: 200000)

**Output**:
- `{output_dir}/ledger.json`: Genesis ledger file
- `{output_dir}/volumes/val[0-N]/rippled.cfg`: Validator configs
- `{output_dir}/docker-compose.yml`: Docker compose file
- `{output_dir}/accounts.json`: Generated account credentials

**Exit Codes**:
- 0: Success
- 1: Invalid parameters
- 2: File write error
- 3: Validation error

**Example**:
```bash
gen auto --accounts 50 --validators 5 --output-dir ./my-testnet
```

### 2. Generate Ledger State

**Command**: `gen ledger`

**Purpose**: Generate genesis ledger JSON file with pre-configured accounts and trustlines

**Usage**:
```bash
gen ledger [OPTIONS]
```

**Options**:
- `--accounts INTEGER`: Number of accounts (default: 10)
- `--balance TEXT`: Default account balance in XRP (default: "100000")
- `--currency TEXT`: Trustline currency code (repeatable)
- `--trustline TEXT`: Define trustline as "account1:account2:currency:limit" (repeatable)
- `--reference-fee INTEGER`: Base transaction fee (default: 10)
- `--account-reserve INTEGER`: Account reserve (default: 2000000)
- `--owner-reserve INTEGER`: Owner reserve (default: 200000)
- `--amendments FILE`: Load amendments from file (default: embedded list)
- `--output FILE`: Output ledger file path (default: `./ledger.json`)

**Output**: `ledger.json` - Genesis ledger file

**Exit Codes**:
- 0: Success
- 1: Invalid parameters
- 2: File write error
- 3: Validation error (balance/reserve mismatch)

**Examples**:
```bash
# Generate basic ledger with 20 accounts
gen ledger --accounts 20 --output ./testnet/ledger.json

# Generate with trustlines
gen ledger --accounts 5 \
  --trustline "alice:bob:USD:1000000" \
  --trustline "bob:carol:EUR:500000" \
  --output ./ledger.json

# Custom reserves
gen ledger --accounts 10 \
  --account-reserve 1000000 \
  --owner-reserve 200000 \
  --reference-fee 10
```

**Validation**:
- Sum of all balances must equal total coins (100B XRP)
- All account balances must meet reserve requirements
- Trustline accounts must exist
- Currency codes must be valid (3-char or 40-char hex)

### 3. Generate Validator Configurations

**Command**: `gen validators`

**Purpose**: Generate rippled.cfg files for each validator with keys and network configuration

**Usage**:
```bash
gen validators [OPTIONS]
```

**Options**:
- `--count INTEGER`: Number of validators (default: 5, min: 4)
- `--output-dir PATH`: Output directory (default: `./volumes`)
- `--prefix TEXT`: Validator name prefix (default: `val`)
- `--peer-port INTEGER`: Peer protocol port (default: 51235)
- `--rpc-port INTEGER`: Base RPC port (default: 5005)
- `--ws-port INTEGER`: Base WebSocket port (default: 6006)
- `--reference-fee INTEGER`: Fee for voting section (default: 10)
- `--account-reserve INTEGER`: Reserve for voting section (default: 2000000)
- `--owner-reserve INTEGER`: Reserve for voting section (default: 200000)
- `--keygen-method TEXT`: Key generation method: "xrpl" or "docker" (default: "xrpl")

**Output**:
- `{output_dir}/val0/rippled.cfg`
- `{output_dir}/val1/rippled.cfg`
- `{output_dir}/val[2-N]/rippled.cfg`
- `{output_dir}/validators.json`: Validator public keys and seeds

**Exit Codes**:
- 0: Success
- 1: Invalid parameters
- 2: File write error
- 3: Key generation error

**Examples**:
```bash
# Generate 7 validators
gen validators --count 7 --output-dir ./testnet/volumes

# Custom ports
gen validators --count 5 \
  --peer-port 51235 \
  --rpc-port 5005 \
  --ws-port 6006

# Docker-based key generation
gen validators --count 5 --keygen-method docker
```

**Validation**:
- Validator count >= 4 (Byzantine fault tolerance requirement)
- All ports must be valid (1-65535)
- Voting parameters must match ledger FeeSettings

### 4. Generate Docker Compose

**Command**: `gen compose`

**Purpose**: Generate docker-compose.yml for running validator network

**Usage**:
```bash
gen compose [OPTIONS]
```

**Options**:
- `--validators INTEGER`: Number of validators (default: 5)
- `--output FILE`: Output file path (default: `./docker-compose.yml`)
- `--network-name TEXT`: Docker network name (default: `xrpl_net`)
- `--image TEXT`: Rippled Docker image (default: `rippleci/rippled`)
- `--tag TEXT`: Image tag (default: `develop`)
- `--volumes-dir PATH`: Validator volumes directory (default: `./volumes`)
- `--ledger-file PATH`: Genesis ledger file path (default: `./ledger.json`)
- `--expose-ports`: Expose validator ports to host (default: false)

**Output**: `docker-compose.yml` - Docker compose configuration

**Exit Codes**:
- 0: Success
- 1: Invalid parameters
- 2: File write error

**Examples**:
```bash
# Basic generation
gen compose --validators 5 --output ./testnet/docker-compose.yml

# Custom image and network
gen compose --validators 5 \
  --image rippleci/rippled \
  --tag develop \
  --network-name my_xrpl_net

# Expose ports for debugging
gen compose --validators 5 --expose-ports
```

**Validation**:
- Validator count must match generated configs
- Volumes directory must exist
- Ledger file must exist

## Configuration File Support

**Config File**: `.env` or specified via `--config`

**Format**: Environment variables (key=value pairs)

**Supported Variables**:
```bash
# Ledger Configuration
GL_NUM_ACCOUNTS=10
GL_BALANCE=100000000000
GL_REFERENCE_FEE=10
GL_ACCOUNT_RESERVE=2000000
GL_OWNER_RESERVE=200000

# Validator Configuration
GL_NUM_VALIDATORS=5
GL_VALIDATOR_PREFIX=val
GL_PEER_PORT=51235

# Docker Configuration
GL_NETWORK_NAME=xrpl_net
GL_VALIDATOR_IMAGE=rippleci/rippled
GL_VALIDATOR_IMAGE_TAG=develop

# Output Paths
GL_OUTPUT_DIR=./testnet
GL_LEDGER_FILE=./ledger.json
```

**Usage**:
```bash
# Create .env file
cat > .env << EOF
GL_NUM_ACCOUNTS=50
GL_NUM_VALIDATORS=7
GL_OUTPUT_DIR=./custom-testnet
EOF

# Run with config
gen auto
```

## Output File Formats

### ledger.json

**Format**: JSON

**Schema**:
```json
{
  "ledger": {
    "accepted": boolean,
    "accountState": [
      {
        "LedgerEntryType": "AccountRoot" | "RippleState" | "FeeSettings" | "Amendments",
        ...
      }
    ],
    "close_time_resolution": integer,
    "totalCoins": string,
    "total_coins": string
  }
}
```

### rippled.cfg

**Format**: INI-style configuration

**Required Sections**:
- `[server]`: Server configuration
- `[port_peer]`: Peer protocol port
- `[port_rpc_admin_local]`: RPC admin port
- `[port_ws_admin_local]`: WebSocket admin port
- `[node_db]`: Database configuration
- `[database_path]`: Database path
- `[ledger_history]`: History setting
- `[validators]`: UNL (Unique Node List)
- `[ips_fixed]`: Fixed peer connections
- `[voting]`: Fee voting parameters
- `[validation_seed]`: Validator's validation seed (validators only)

### docker-compose.yml

**Format**: YAML (Docker Compose v3)

**Required Services**:
- `val0...valN`: Validator services
- `rippled`: Non-validator hub node (optional)

**Required Networks**:
- Custom bridge network for validator communication

## Error Handling

**Error Response Format** (JSON when `--json` flag used):
```json
{
  "error": "Error message",
  "code": "ERROR_CODE",
  "details": {
    "field": "Validation details"
  }
}
```

**Common Error Codes**:
- `INVALID_PARAMETER`: Invalid command-line parameter
- `VALIDATION_ERROR`: Data validation failed
- `FILE_ERROR`: File read/write error
- `KEY_GENERATION_ERROR`: Validator key generation failed
- `INSUFFICIENT_BALANCE`: Account balances don't meet reserves
- `BALANCE_MISMATCH`: Sum of balances doesn't equal total coins
- `DUPLICATE_IDENTIFIER`: Duplicate account identifier
- `MISSING_ACCOUNT`: Referenced account doesn't exist

## Success Output

**Standard Output** (text format):
```
✓ Generated 10 accounts
✓ Generated 2 trustlines
✓ Created genesis ledger: ./ledger.json
✓ Generated 5 validator configs
✓ Created docker-compose.yml
✓ Environment ready: ./testnet

To start the network:
  cd ./testnet
  docker-compose up -d

To check status:
  docker-compose ps
  docker exec rippled rippled server_info
```

**JSON Output** (`--json` flag):
```json
{
  "success": true,
  "files_generated": [
    "./testnet/ledger.json",
    "./testnet/volumes/val0/rippled.cfg",
    "./testnet/volumes/val1/rippled.cfg",
    "./testnet/volumes/val2/rippled.cfg",
    "./testnet/volumes/val3/rippled.cfg",
    "./testnet/volumes/val4/rippled.cfg",
    "./testnet/docker-compose.yml"
  ],
  "accounts_generated": 10,
  "validators_generated": 5,
  "network_name": "xrpl_net",
  "next_steps": [
    "cd ./testnet",
    "docker-compose up -d"
  ]
}
```

## Validation Rules

**Cross-Command Consistency**:
1. Validator count must be consistent across `gen validators` and `gen compose`
2. Reserve settings must match between `gen ledger` and `gen validators`
3. Output directory structure must be consistent:
   ```
   testnet/
   ├── ledger.json
   ├── volumes/
   │   ├── val0/rippled.cfg
   │   ├── val1/rippled.cfg
   │   └── ...
   └── docker-compose.yml
   ```

## Examples: Complete Workflows

### Workflow 1: Quick Start (Default Settings)
```bash
gen auto
cd ./testnet
docker-compose up -d
```

### Workflow 2: Custom Configuration
```bash
# Generate ledger with specific settings
gen ledger --accounts 50 \
  --balance 1000000000000 \
  --account-reserve 1000000 \
  --output ./custom/ledger.json

# Generate 7 validators
gen validators --count 7 \
  --reference-fee 10 \
  --account-reserve 1000000 \
  --owner-reserve 200000 \
  --output-dir ./custom/volumes

# Generate docker-compose
gen compose --validators 7 \
  --volumes-dir ./custom/volumes \
  --ledger-file ./custom/ledger.json \
  --output ./custom/docker-compose.yml

# Deploy
cd ./custom
docker-compose up -d
```

### Workflow 3: With Trustlines
```bash
gen ledger --accounts 10 \
  --trustline "0:1:USD:1000000000000" \
  --trustline "1:2:EUR:500000000000" \
  --trustline "2:3:GBP:750000000000" \
  --output ./ledger.json

gen validators --count 5 --output-dir ./volumes
gen compose --validators 5 --output ./docker-compose.yml
docker-compose up -d
```

## CLI Implementation Notes

**Current Implementation**: `src/generate_ledger/cli/main.py` (Typer-based CLI)

**Key Classes**:
- `AccountConfig`: Account generation settings
- `RippledConfigSpec`: Validator configuration
- `ComposeConfig`: Docker compose settings

**Extension Points**:
- Add `--mpt` flag for MPT generation (Phase 2)
- Add `--amm` flag for AMM initialization (Phase 2)
- Add `--vault` flag for Vault/lending primitives (Phase 3)
