"""Tests for the compose CLI (generate_ledger.cli.compose)."""

from typer.testing import CliRunner

from generate_ledger.cli.compose import app as compose_app
from generate_ledger.cli.ledger import app as ledger_app
from generate_ledger.cli.xrpld_cfg import app as xrpld_app

runner = CliRunner()


class TestComposeCommand:
    def test_missing_volumes_dir_errors(self, tmp_path):
        """Compose requires a volumes/ dir from gen xrpld."""
        result = runner.invoke(compose_app, ["-b", str(tmp_path)])
        assert result.exit_code != 0
        assert "volumes" in result.output.lower() or "does not exist" in result.output.lower()

    def test_missing_ledger_file_errors(self, tmp_path):
        """Compose errors if --ledger-file points to a nonexistent file."""
        (tmp_path / "volumes").mkdir()
        result = runner.invoke(
            compose_app,
            ["-b", str(tmp_path), "-l", str(tmp_path / "nonexistent.json")],
        )
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_compose_without_ledger(self, tmp_path):
        """Compose without --ledger-file produces a compose file with no ledger mount."""
        (tmp_path / "volumes").mkdir()
        result = runner.invoke(
            compose_app,
            ["-b", str(tmp_path), "--validators", "2"],
        )
        assert result.exit_code == 0, result.output
        compose_file = tmp_path / "docker-compose.yml"
        assert compose_file.exists()
        content = compose_file.read_text()
        assert "ledger.json" not in content

    def test_compose_with_ledger(self, tmp_path):
        """Compose with --ledger-file mounts the ledger into containers."""
        (tmp_path / "volumes").mkdir()
        ledger = tmp_path / "ledger.json"
        ledger.write_text("{}")
        result = runner.invoke(
            compose_app,
            ["-b", str(tmp_path), "--validators", "2", "-l", str(ledger)],
        )
        assert result.exit_code == 0, result.output
        compose_file = tmp_path / "docker-compose.yml"
        assert compose_file.exists()
        content = compose_file.read_text()
        assert "ledger.json" in content

    def test_compose_validator_count(self, tmp_path):
        """Compose produces the requested number of validator services."""
        (tmp_path / "volumes").mkdir()
        result = runner.invoke(
            compose_app,
            ["-b", str(tmp_path), "--validators", "3"],
        )
        assert result.exit_code == 0, result.output
        content = (tmp_path / "docker-compose.yml").read_text()
        assert "val0" in content
        assert "val1" in content
        assert "val2" in content


class TestThreeStepWorkflow:
    """End-to-end test: gen ledger -> gen xrpld -> gen compose."""

    def test_ledger_then_xrpld_then_compose(self, tmp_path):
        # Step 1: Generate ledger
        ledger_result = runner.invoke(
            ledger_app,
            ["--accounts", "5", "-o", str(tmp_path)],
        )
        assert ledger_result.exit_code == 0, ledger_result.output
        ledger_file = tmp_path / "ledger.json"
        assert ledger_file.exists()

        # Step 2: Generate xrpld configs
        volumes_dir = tmp_path / "volumes"
        xrpld_result = runner.invoke(
            xrpld_app,
            ["-b", str(volumes_dir), "-v", "3"],
        )
        assert xrpld_result.exit_code == 0, xrpld_result.output
        assert (volumes_dir / "val0" / "xrpld.cfg").exists()

        # Step 3: Generate compose with ledger
        compose_result = runner.invoke(
            compose_app,
            ["-b", str(tmp_path), "--validators", "3", "-l", str(ledger_file)],
        )
        assert compose_result.exit_code == 0, compose_result.output

        # Verify compose file
        compose_file = tmp_path / "docker-compose.yml"
        assert compose_file.exists()
        content = compose_file.read_text()
        # Has all 3 validators + hub
        assert "val0" in content
        assert "val1" in content
        assert "val2" in content
        assert "xrpld" in content
        # Ledger is mounted
        assert "ledger.json" in content

    def test_ledger_then_xrpld_then_compose_no_ledger(self, tmp_path):
        """Same workflow but compose without mounting the ledger."""
        # Step 1: Generate ledger (still generate it, just don't mount)
        ledger_result = runner.invoke(
            ledger_app,
            ["--accounts", "5", "-o", str(tmp_path)],
        )
        assert ledger_result.exit_code == 0, ledger_result.output

        # Step 2: Generate xrpld configs
        volumes_dir = tmp_path / "volumes"
        xrpld_result = runner.invoke(
            xrpld_app,
            ["-b", str(volumes_dir), "-v", "2"],
        )
        assert xrpld_result.exit_code == 0, xrpld_result.output

        # Step 3: Generate compose WITHOUT --ledger-file
        compose_result = runner.invoke(
            compose_app,
            ["-b", str(tmp_path), "--validators", "2"],
        )
        assert compose_result.exit_code == 0, compose_result.output

        compose_file = tmp_path / "docker-compose.yml"
        assert compose_file.exists()
        content = compose_file.read_text()
        assert "val0" in content
        assert "val1" in content
        assert "ledger.json" not in content
