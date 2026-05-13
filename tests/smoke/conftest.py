"""Shared fixtures for smoke tests.

Test-specific fixtures (testnet_dir, network, mpt_issuance_id, etc.) stay
in individual test files because each smoke test generates a different
genesis ledger. Only fixtures that are genuinely shared across all smoke
tests live here.
"""

import uuid

import pytest

from tests.smoke._helpers import load_accounts


@pytest.fixture(scope="module")
def container_name(request) -> str:
    """Unique container name per test module — keeps concurrent runs disjoint.

    Uses the test module's basename (e.g. "test_amm_autobridge" -> "autobridge")
    so the container is identifiable in `docker ps` while a test is running.
    """
    suffix = request.module.__name__.rsplit(".", 1)[-1].removeprefix("test_")
    return f"smoke_{suffix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def accounts(testnet_dir):
    """Load (address, seed) pairs from the test's testnet_dir."""
    return load_accounts(testnet_dir)
