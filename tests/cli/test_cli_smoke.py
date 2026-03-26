from click.testing import CliRunner

from generate_ledger import __app_name__
from generate_ledger.cli.main import cli as app

runner = CliRunner()


def test_cli_help():
    r = runner.invoke(app, ["--help"], prog_name=__app_name__)
    assert r.exit_code == 0, r.output
    assert "ledger" in r.output
    assert "xrpld" in r.output
