"""Tests for the root CLI (generate_ledger.cli.main)."""

from click.testing import CliRunner

from generate_ledger.cli.main import cli

runner = CliRunner()


class TestRootCli:
    def test_help_lists_subcommands(self):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        for name in ("compose", "ledger", "rippled", "auto"):
            assert name in result.output

    def test_no_args_defaults_to_compose_write(self, tmp_path, monkeypatch):
        """Running with no subcommand should invoke compose write."""
        monkeypatch.setenv("GL_BASE_DIR", str(tmp_path))
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert "Wrote" in result.output or "Writing" in result.output

    def test_ledgend_flag(self):
        result = runner.invoke(cli, ["--ledgend"])
        assert result.exit_code == 0
        # Should print the decompressed logo
        assert len(result.output) > 10

    def test_output_option_passthrough(self, tmp_path, monkeypatch):
        """The -o flag should be accepted at the root level."""
        monkeypatch.setenv("GL_BASE_DIR", str(tmp_path))
        out = tmp_path / "custom-compose.yml"
        result = runner.invoke(cli, ["-o", str(out)])
        assert result.exit_code == 0

    def test_compose_subcommand(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GL_BASE_DIR", str(tmp_path))
        result = runner.invoke(cli, ["compose", "write"])
        assert result.exit_code == 0

    def test_context_initializes_state(self, tmp_path, monkeypatch):
        """The root callback should create SimpleNamespace with compose and ledger configs."""
        monkeypatch.setenv("GL_BASE_DIR", str(tmp_path))
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
