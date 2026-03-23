from click.testing import CliRunner
from ruamel.yaml import YAML

from generate_ledger import __app_name__
from generate_ledger.cli.main import cli as app

yaml = YAML()

runner = CliRunner()


def test_validators_override(tmp_path, monkeypatch):
    out = tmp_path / "docker-compose.yml"

    monkeypatch.setenv("GL_BASE_DIR", str(tmp_path))

    r = runner.invoke(
        app,
        ["compose", "write", "--validators", "10", "-o", str(out)],
        prog_name=__app_name__,
    )
    assert r.exit_code == 0, r.output
    assert out.exists(), "compose file was not created"

    data = yaml.load(out.read_text())
    validators = [name for name in data["services"] if name.startswith("val")]
    assert len(validators) == 10
