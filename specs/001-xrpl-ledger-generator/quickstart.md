# Quickstart Guide: XRPL Custom Ledger Environment Generator

**Feature**: 001-xrpl-ledger-generator
**Date**: 2025-12-10
**Audience**: Developers setting up custom XRPL test environments

## Prerequisites

- Python 3.12+ installed
- Docker and Docker Compose installed
- Git (for cloning repository)
- 4GB+ RAM available for validators
- Basic understanding of XRPL and blockchain concepts

## Installation

### Option 1: Install from Package

```bash
# Install using pip
pip install legleux-generate-ledger

# Verify installation
gen --version
```

### Option 2: Install from Source

```bash
# Clone repository
git clone https://github.com/legleux/generate_ledger.git
cd generate_ledger

# Install with uv (recommended)
uv pip install -e .

# Or install with pip
pip install -e .

# Verify installation
gen --help
```

## Quick Start (5 Minutes)

### 1. Generate Complete Environment

```bash
# Generate everything with defaults (10 accounts, 5 validators)
gen auto --output-dir ./my-testnet

cd ./my-testnet
```

**What this creates**:
- `ledger.json`: Genesis ledger with 10 accounts
- `volumes/val0-4/rippled.cfg`: 5 validator configurations
- `accounts.json`: Account credentials (addresses and seeds)
- `docker-compose.yml`: Docker deployment configuration

### 2. Start the Network

```bash
# Start all validators and rippled node
docker-compose up -d

# Check status
docker-compose ps
```

**Expected output**:
```
NAME      IMAGE                       STATUS       PORTS
val0      rippleci/rippled:develop   Up          0.0.0.0:5006->5005/tcp, 0.0.0.0:6007->6006/tcp
val1      rippleci/rippled:develop   Up
val2      rippleci/rippled:develop   Up
val3      rippleci/rippled:develop   Up
val4      rippleci/rippled:develop   Up
rippled   rippleci/rippled:develop   Up          0.0.0.0:5005->5005/tcp, 0.0.0.0:6006->6006/tcp
```

### 3. Verify Network is Running

```bash
# Check server info
docker exec rippled rippled server_info | jq '.result.info | {ledger_seq: .validated_ledger.seq, consensus: .server_state}'

# Check account balances (using first generated account)
docker exec rippled rippled account_info rAccount... | jq '.result.account_data.Balance'
```

**Expected**:
- Ledger sequence incrementing (consensus working)
- Server state: "full" or "proposing"
- Account balance matching genesis ledger

### 4. Submit a Test Transaction

```bash
# Load first account credentials
ACCOUNT_ADDRESS=$(jq -r '.[0][0]' accounts.json)
ACCOUNT_SEED=$(jq -r '.[0][1]' accounts.json)

# Create a Payment transaction using xrpl-py
python3 << EOF
import json
from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.transactions import Payment
from xrpl.transaction import submit_and_wait
from xrpl.utils import xrp_to_drops

client = JsonRpcClient("http://localhost:5005")
wallet = Wallet.from_seed("$ACCOUNT_SEED")

# Get destination from second account
with open("accounts.json") as f:
    accounts = json.load(f)
    destination = accounts[1][0]

payment = Payment(
    account=wallet.address,
    destination=destination,
    amount=xrp_to_drops(100)  # Send 100 XRP
)

response = submit_and_wait(payment, client, wallet)
print(f"Transaction successful: {response.result['hash']}")
EOF
```

### 5. Stop the Network

```bash
# Stop all containers
docker-compose down

# Stop and remove all data
docker-compose down -v
```

## Common Use Cases

### Use Case 1: Testing with Trustlines

**Goal**: Create test environment with USD/EUR trustlines for DEX testing

```bash
# Generate ledger with trustlines
gen ledger --accounts 5 \
  --trustline "0:1:USD:1000000000000" \
  --trustline "1:2:EUR:500000000000" \
  --trustline "2:3:USD:750000000000" \
  --output ./dex-test/ledger.json

# Generate validators
gen validators --count 5 \
  --output-dir ./dex-test/volumes

# Generate docker-compose
gen compose --validators 5 \
  --volumes-dir ./dex-test/volumes \
  --ledger-file ./dex-test/ledger.json \
  --output ./dex-test/docker-compose.yml

# Start network
cd ./dex-test
docker-compose up -d
```

**Verify trustlines**:
```bash
# Check trustlines for account 0
ACCOUNT_0=$(jq -r '.[0][0]' accounts.json)
docker exec rippled rippled account_lines $ACCOUNT_0
```

### Use Case 2: High-Value Account Testing

**Goal**: Create accounts with large XRP balances for payment testing

```bash
# Generate 20 accounts with 1M XRP each
gen ledger --accounts 20 \
  --balance 1000000000000000 \
  --output ./payments-test/ledger.json

gen validators --count 5 --output-dir ./payments-test/volumes
gen compose --validators 5 --output ./payments-test/docker-compose.yml

cd ./payments-test
docker-compose up -d
```

### Use Case 3: Custom Fee and Reserve Settings

**Goal**: Test with custom fee/reserve settings to simulate different network conditions

```bash
# Low reserves for rapid testing
gen auto --accounts 100 \
  --validators 5 \
  --reference-fee 1000 \
  --account-reserve 1000000 \
  --owner-reserve 100000 \
  --output-dir ./low-reserve-test

cd ./low-reserve-test
docker-compose up -d
```

### Use Case 4: Large Validator Network

**Goal**: Test consensus with 7+ validators

```bash
# Generate 7-validator network
gen auto --accounts 50 \
  --validators 7 \
  --output-dir ./large-network

cd ./large-network
docker-compose up -d

# Verify consensus with 7 validators
docker exec rippled rippled validators
```

## Advanced Configuration

### Using Configuration Files

Create `.env` file:
```bash
# .env
GL_NUM_ACCOUNTS=50
GL_NUM_VALIDATORS=7
GL_BALANCE=500000000000000
GL_REFERENCE_FEE=10
GL_ACCOUNT_RESERVE=2000000
GL_OWNER_RESERVE=200000
GL_OUTPUT_DIR=./custom-testnet
GL_NETWORK_NAME=my_xrpl_net
```

Run with config:
```bash
gen auto
```

### Custom Validator Keys

**Using Docker-based key generation**:
```bash
gen validators --count 5 \
  --keygen-method docker \
  --output-dir ./volumes
```

**Using Python-based generation** (default):
```bash
gen validators --count 5 \
  --keygen-method xrpl \
  --output-dir ./volumes
```

### Exposing Validator Ports

For debugging or external access:
```bash
gen compose --validators 5 \
  --expose-ports \
  --output ./docker-compose.yml
```

This exposes RPC/WS ports for all validators:
- val0: 5006:5005, 6007:6006
- val1: 5007:5005, 6008:6006
- val2: 5008:5005, 6009:6006
- etc.

## Troubleshooting

### Issue: Validators Not Reaching Consensus

**Symptoms**:
- Ledger sequence not incrementing
- Server state stuck at "connected" or "syncing"

**Solutions**:
```bash
# Check validator connectivity
docker exec val0 rippled peers

# Check UNL configuration
docker exec val0 cat /etc/opt/ripple/rippled.cfg | grep -A 10 "\[validators\]"

# Verify all validators are running
docker-compose ps

# Check logs
docker-compose logs val0
```

**Common causes**:
- Less than 4 validators online (need 80% quorum)
- Validator configs have mismatched UNLs
- Network connectivity issues between containers

### Issue: "Insufficient Reserve" Errors

**Symptoms**:
- Cannot submit transactions
- Accounts show insufficient balance errors

**Solution**:
Regenerate ledger with higher reserves or account balances:
```bash
gen ledger --accounts 10 \
  --balance 100000000000000 \
  --account-reserve 2000000 \
  --owner-reserve 200000 \
  --output ./ledger.json
```

### Issue: Docker Containers Failing to Start

**Symptoms**:
- Containers exit immediately
- Health check failures

**Solutions**:
```bash
# Check container logs
docker logs val0

# Verify ledger file exists
ls -la ./ledger.json

# Verify config files exist
ls -la ./volumes/val0/rippled.cfg

# Check Docker network
docker network ls | grep xrpl

# Restart with fresh state
docker-compose down -v
docker-compose up -d
```

### Issue: Port Conflicts

**Symptoms**:
- "Address already in use" errors
- Containers fail to start

**Solutions**:
```bash
# Check what's using the ports
lsof -i :5005
lsof -i :6006

# Use different host ports
gen compose --validators 5 --output ./docker-compose.yml
# Edit docker-compose.yml to change port mappings

# Or use a custom network name
gen auto --network-name xrpl_net_2 --output-dir ./testnet2
```

## Monitoring and Debugging

### Check Network Health

```bash
# Server status
docker exec rippled rippled server_info

# Validator list
docker exec rippled rippled validators

# Peer connections
docker exec val0 rippled peers

# Ledger progress
watch -n 1 'docker exec rippled rippled ledger_closed | jq .result.ledger_index'
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific validator
docker-compose logs -f val0

# rippled node only
docker-compose logs -f rippled

# Last 100 lines
docker-compose logs --tail=100
```

### Access RPC Directly

```bash
# Using curl
curl -X POST http://localhost:5005 \
  -H "Content-Type: application/json" \
  -d '{"method": "server_info"}'

# Using xrpl-py
python3 -c "
from xrpl.clients import JsonRpcClient
client = JsonRpcClient('http://localhost:5005')
print(client.request({'method': 'server_info'}))
"
```

### Access WebSocket

```python
import asyncio
from xrpl.clients import AsyncWebsocketClient

async def main():
    async with AsyncWebsocketClient("ws://localhost:6006") as client:
        response = await client.request({"method": "server_info"})
        print(response)

asyncio.run(main())
```

## Next Steps

### Phase 2: Adding MPT and AMM (Coming Soon)

Once the network is running, you'll be able to create MPTs and AMMs using post-genesis initialization:

```bash
# Initialize MPTs (future feature)
gen init-mpts --config mpt-config.json

# Initialize AMMs (future feature)
gen init-amms --config amm-config.json
```

### Phase 3: Lending Protocol Support (Roadmap)

Future support for Vault-based lending:

```bash
# Initialize vaults (future feature)
gen init-vaults --config vault-config.json
```

## Cleanup

### Remove Specific Network

```bash
cd ./my-testnet
docker-compose down -v
cd ..
rm -rf ./my-testnet
```

### Remove All Generated Networks

```bash
# Stop all containers
docker stop $(docker ps -a -q --filter ancestor=rippleci/rippled:develop)

# Remove containers
docker rm $(docker ps -a -q --filter ancestor=rippleci/rippled:develop)

# Remove networks
docker network prune

# Clean up volumes
docker volume prune
```

## Resources

- **Documentation**: [XRPL.org](https://xrpl.org)
- **xrpl-py Library**: [GitHub](https://github.com/XRPLF/xrpl-py)
- **Rippled**: [GitHub](https://github.com/XRPLF/rippled)
- **Issue Tracker**: [Report issues](https://github.com/legleux/generate_ledger/issues)

## FAQ

**Q: How many validators do I need?**
A: Minimum 4 for Byzantine fault tolerance. 5 is recommended for test networks. You can use up to 10 for larger tests.

**Q: Can I use this for production?**
A: No. This tool is designed for test and development environments only. Production networks require different security and operational procedures.

**Q: How long does it take to start consensus?**
A: Typically 5-10 seconds after all validators are healthy and connected.

**Q: Can I modify the genesis ledger after creation?**
A: No. The genesis ledger is immutable. You must regenerate and restart the network to make changes.

**Q: How do I add more accounts after genesis?**
A: You can't pre-generate more accounts, but you can create them via transactions after the network starts using standard XRPL account creation methods.

**Q: What's the difference between val0 and other validators?**
A: val0 is the bootstrap validator that loads the genesis ledger. Other validators sync from the network. They all have equal consensus weight.

**Q: Can I run multiple test networks simultaneously?**
A: Yes! Use different output directories and network names:
```bash
gen auto --output-dir ./testnet1 --network-name xrpl_net_1
gen auto --output-dir ./testnet2 --network-name xrpl_net_2
```

**Q: How do I upgrade rippled version?**
A: Change the image tag in docker-compose.yml:
```yaml
image: rippleci/rippled:2.0.0  # or any other tag
```

## Summary

You've learned how to:
- ✅ Generate complete XRPL test environments in minutes
- ✅ Create custom ledgers with accounts and trustlines
- ✅ Deploy multi-validator networks with Docker
- ✅ Verify network health and submit transactions
- ✅ Troubleshoot common issues
- ✅ Configure custom fee and reserve settings

For more advanced usage, see the full documentation in the specification files.
