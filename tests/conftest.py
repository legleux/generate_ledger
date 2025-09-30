import pytest
from generate_ledger.compose import ComposeConfig
from pathlib import Path
import json

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
