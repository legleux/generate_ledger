import json
from pathlib import Path

import pytest

from generate_ledger.compose import ComposeConfig
from gl.accounts import Account
from gl.amendments import get_enabled_amendment_hashes


@pytest.fixture(autouse=True)
def _sandbox_base_dir(tmp_path, monkeypatch):
    """Redirect GL_BASE_DIR to a pytest tmp_path so tests don't touch real files."""
    monkeypatch.setenv("GL_BASE_DIR", str(tmp_path))

@pytest.fixture
def config(tmp_path) -> ComposeConfig:
    """ComposeConfig pointed at a per-test temp directory.
    Will use the GL_BASE_DIR from _sandbox_base_dir()
    """
    return ComposeConfig(base_dir=tmp_path)  # picks up  from the autouse fixture

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
def template_dir(tests_root: Path) -> Path:
    return tests_root / "data"

@pytest.fixture(scope="session")
def amendments(data_dir: Path):
    with (data_dir / "amendments.json").open() as f:
        return json.load(f)


# --- Deterministic account fixtures from test data ---

ALICE_ADDRESS = "rDG31rPVQAXDarm3bUwJBstrKVQCG3wLbK"
ALICE_SEED = "ssyEbTBiw519ozYhYqNWBZAWBDWQW"
BOB_ADDRESS = "rLAeC2Z5Mvp9XhxCrc978s9PafwrwMYdAS"
BOB_SEED = "ssjZCaCnESvTkvRwY2RuXFKTC1Ayb"
GENESIS_ADDRESS = "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh"

# Known-good indices from a running rippled node (tests/data/ledger/testnet/volumes/ledger.json)
GENESIS_INDEX = "2B6AC232AA4C4BE41BF49D2459FA4A0347E1B543A4C92FCEE0821C0201E2E9A8"
ALICE_INDEX = "91FAA5339CCF27916B9EA43C5286F354A430DD6A4DD32E5612BC8616343BC355"
BOB_INDEX = "0C6E2AF3D9E921CEF30BD7A1B57B46A0995BAFCF3C1A26148003084810DE259F"
AMENDMENTS_INDEX = "7DB0788C020F02780A673DC74757F23823FA3014C1866E72CC4CD8B226CD6EF4"
FEE_SETTINGS_INDEX = "4BC50C9B0D8515D3EAAE1E74B29A95804346C491EE1A95BF25E4AAB854A6A651"


@pytest.fixture
def alice_account() -> Account:
    return Account(ALICE_ADDRESS, ALICE_SEED)


@pytest.fixture
def bob_account() -> Account:
    return Account(BOB_ADDRESS, BOB_SEED)


@pytest.fixture
def two_accounts(alice_account, bob_account) -> list[Account]:
    return [alice_account, bob_account]


@pytest.fixture
def genesis_address() -> str:
    return GENESIS_ADDRESS


@pytest.fixture(scope="session")
def sample_amendment_hashes(data_dir: Path) -> list[str]:
    """Load enabled amendment hashes from test fixture."""
    amendments_file = str(data_dir / "amendment_list_dev_20250907.json")
    return get_enabled_amendment_hashes(source=amendments_file)
