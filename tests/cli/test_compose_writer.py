"""Tests for generate_ledger.commands.compose_writer."""

from pathlib import Path
from types import SimpleNamespace

from click.testing import CliRunner

from generate_ledger.commands.compose_writer import _do_compose_write, compose_write
from generate_ledger.compose import ComposeConfig
from generate_ledger.ledger import LedgerConfig


def _make_state(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        compose=ComposeConfig(base_dir=tmp_path),
        ledger=LedgerConfig(),
    )


class TestDoComposeWrite:
    def test_writes_default(self, tmp_path):
        state = _make_state(tmp_path)
        _do_compose_write(state, None, None, None, None, None, None)
        assert (tmp_path / "docker-compose.yml").exists()

    def test_validators_override(self, tmp_path):
        state = _make_state(tmp_path)
        _do_compose_write(state, None, 3, None, None, None, None)
        import ruamel.yaml
        yml = ruamel.yaml.YAML()
        data = yml.load((tmp_path / "docker-compose.yml").open())
        validators = [k for k in data["services"] if k.startswith("val")]
        assert len(validators) == 3

    def test_output_file_override(self, tmp_path):
        state = _make_state(tmp_path)
        custom_path = tmp_path / "custom.yml"
        _do_compose_write(state, custom_path, None, None, None, None, None)
        assert custom_path.exists()


class TestComposeWriteClickCommand:
    def test_basic_invocation(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GL_BASE_DIR", str(tmp_path))
        runner = CliRunner()
        state = _make_state(tmp_path)
        result = runner.invoke(compose_write, [], obj=state)
        assert result.exit_code == 0, result.output
        assert "Wrote" in result.output

    def test_with_validators_flag(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GL_BASE_DIR", str(tmp_path))
        runner = CliRunner()
        state = _make_state(tmp_path)
        result = runner.invoke(compose_write, ["-v", "2"], obj=state)
        assert result.exit_code == 0, result.output
