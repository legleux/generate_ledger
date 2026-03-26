"""Tests for the root CLI (generate_ledger.cli.main)."""

from click.testing import CliRunner

from generate_ledger.cli.main import cli

runner = CliRunner()


class TestRootCli:
    def test_help_lists_subcommands(self):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        for name in ("ledger", "xrpld"):
            assert name in result.output

    def test_no_args_runs_full_pipeline(self, tmp_path, monkeypatch):
        """Running with no subcommand should run the full 3-step pipeline."""
        monkeypatch.setenv("GL_BASE_DIR", str(tmp_path))
        result = runner.invoke(cli, ["-o", str(tmp_path), "--accounts", "2", "-v", "2"])
        assert result.exit_code == 0, result.output
        assert "Step 1/3" in result.output
        assert (tmp_path / "ledger.json").exists()

    def test_ledgend_flag(self):
        result = runner.invoke(cli, ["--ledgend"])
        assert result.exit_code == 0
        assert len(result.output) > 10
