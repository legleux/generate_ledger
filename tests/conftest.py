import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import pytest
import xrpl
from xrpl.core.keypairs import generate_seed
from xrpl.wallet import Wallet

pytest_plugins = ["fixtures.accounts", "pytest_asyncio"]


@pytest.fixture(scope="session")
def project_root(pytestconfig) -> Path:
    return pytestconfig.rootpath


@pytest.fixture(scope="session")
def tests_root(project_root: Path) -> Path:
    return project_root / "tests"


@pytest.fixture(scope="session")
def data_dir(tests_root: Path) -> Path:
    return tests_root / "data"


@pytest.fixture(scope="session")
def account_vectors(data_dir: Path):
    with (data_dir / "account_vectors.json").open() as f:
        return json.load(f)


@pytest.fixture(scope="session")
def ripplestate_vectors(data_dir: Path):
    with (data_dir / "ripplestate_vectors.json").open() as f:
        return json.load(f)


# @pytest.fixture()
# def setup_ledger():
#     print("setup")
#     yield "resource"
#     print("teardown")


def pytest_addoption(parser):
    parser.addoption("--algo", help="Crypto algo (ed25519, secp256k1)")
    parser.addoption("--network", help="XRPL network (mainnet, testnet, devnet)")
    parser.addoption("--seed-length", type=int, help="Seed length in bytes")
    parser.addoption("--key-encoding", help="Encoding (hex, base58, bech32)")

    # optional pytest.ini / pyproject.toml defaults
    parser.addini("default_algo", "Default crypto algo for tests")
    parser.addini("default_network", "Default network for tests")
    parser.addini("default_seed_length", "Default seed length")
    parser.addini("default_key_encoding", "Default key encoding")


# Marker to override per-test:
#    @pytest.mark.algo("secp256k1")
def pytest_configure(config):
    config.addinivalue_line("markers", "algo(name): override crypto algo for this test")

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


@dataclass(frozen=True)
class TestConfig:
    algo: str
    network: str
    seed_length: int
    key_encoding: str


@pytest.fixture(scope="session")
def test_config(pytestconfig) -> TestConfig:
    env = os.environ

    return TestConfig(
        algo=(
            pytestconfig.getoption("--algo") or env.get("TEST_ALGO") or pytestconfig.getini("default_algo") or "ed25519"
        ),
        network=(
            pytestconfig.getoption("--network")
            or env.get("TEST_NETWORK")
            or pytestconfig.getini("default_network")
            or "testnet"
        ),
        seed_length=(
            pytestconfig.getoption("--seed-length")
            or env.get("TEST_SEED_LENGTH")
            or pytestconfig.getini("default_seed_length")
            or 16
        ),
        key_encoding=(
            pytestconfig.getoption("--key-encoding")
            or env.get("TEST_KEY_ENCODING")
            or pytestconfig.getini("default_key_encoding")
            or "hex"
        ),
    )


@pytest.fixture
def algo(request, test_config: TestConfig) -> str:
    m = request.node.get_closest_marker("algo")
    return m.args[0] if m and m.args else test_config.algo
