"""Tests for generate_ledger.cli.auto.build_command_from_defaults."""

import click
from types import SimpleNamespace

from generate_ledger.cli.auto import build_command_from_defaults
from generate_ledger.compose import ComposeConfig
from generate_ledger.ledger import LedgerConfig


class TestBuildCommandFromDefaults:
    def test_returns_click_command(self):
        cmd = build_command_from_defaults(
            command_name="test-write",
            command_key="compose-write",
            model_cls=ComposeConfig,
            state_attr="compose",
            runner=lambda base, overrides, out: None,
        )
        assert isinstance(cmd, click.Command)
        assert cmd.name == "test-write"

    def test_command_has_expected_params(self):
        cmd = build_command_from_defaults(
            command_name="test-write",
            command_key="compose-write",
            model_cls=ComposeConfig,
            state_attr="compose",
            runner=lambda base, overrides, out: None,
        )
        param_names = [p.name for p in cmd.params]
        assert "validators" in param_names
        assert "output_file" in param_names

    def test_command_invocable(self, tmp_path, monkeypatch):
        """The generated command should be invocable via CliRunner."""
        monkeypatch.setenv("GL_BASE_DIR", str(tmp_path))
        captured = {}

        def spy_runner(base, overrides, output_file):
            captured["base"] = base
            captured["overrides"] = overrides

        cmd = build_command_from_defaults(
            command_name="test-write",
            command_key="compose-write",
            model_cls=ComposeConfig,
            state_attr="compose",
            runner=spy_runner,
        )
        runner = click.testing.CliRunner()
        state = SimpleNamespace(
            compose=ComposeConfig(base_dir=tmp_path),
            ledger=LedgerConfig(),
        )
        result = runner.invoke(cmd, [], obj=state)
        assert result.exit_code == 0, result.output
        assert isinstance(captured["base"], ComposeConfig)
