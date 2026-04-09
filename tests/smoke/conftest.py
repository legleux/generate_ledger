"""Shared fixtures for smoke tests.

Provides: accounts, container_name, network (standalone mode).
Each test module must provide: testnet_dir fixture, rpc_port fixture.
The payment_ring test provides its own network fixture (docker-compose).
"""

import json
import os
import uuid

import pytest

from tests.smoke.helpers import start_standalone_node, stop_container

KEEP_NETWORK = os.environ.get("SMOKE_KEEP_NETWORK", "0") == "1"


@pytest.fixture(scope="module")
def accounts(testnet_dir):
    """Load accounts from accounts.json."""
    data = json.loads((testnet_dir / "accounts.json").read_text())
    return [(addr, seed) for addr, seed in data]


@pytest.fixture(scope="module")
def container_name(request):
    """Unique container name derived from the test module."""
    short_name = request.module.__name__.rsplit(".", 1)[-1].removeprefix("test_")
    return f"smoke_{short_name}_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def network(testnet_dir, container_name, rpc_port):
    """Start a standalone xrpld node, yield sync client, teardown on exit."""
    ledger_path = str(testnet_dir / "ledger.json")
    cfg_dir = str(testnet_dir / "xrpld")

    print(f"\n  Testnet dir: {testnet_dir}")

    client = start_standalone_node(container_name, rpc_port, cfg_dir, ledger_path)

    yield client

    if KEEP_NETWORK:
        print("\n  SMOKE_KEEP_NETWORK=1: leaving container running.")
        print(f"  Container: {container_name}")
        print(f"  To tear down: docker rm -f {container_name}")
    else:
        stop_container(container_name)
