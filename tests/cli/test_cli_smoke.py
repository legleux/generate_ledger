from typer.testing import CliRunner

from generate_ledger import __app_name__
from generate_ledger.cli import app

runner = CliRunner()

def test_cli_help():
    r = runner.invoke(app, ["--help"], prog_name=__app_name__)
    assert r.exit_code == 0, r.output
    assert __app_name__ in r.output
    assert "compose" in r.output

def test_compose_write(tmp_path):
    out = tmp_path / "dc.yml"
    r = runner.invoke(app, ["compose", "write", "-o", str(out)], prog_name=__app_name__)
    assert r.exit_code == 0, r.output
    assert out.exists()
