"""CLI tests for the 'auto' command using Typer's test runner."""

import json

from typer.testing import CliRunner

from generate_ledger.cli.auto_cmd import app

runner = CliRunner()


class TestAutoCommand:
    def test_basic_invocation(self, tmp_path):
        result = runner.invoke(app, ["-o", str(tmp_path), "-v", "2", "--accounts", "3"])
        assert result.exit_code == 0, result.output
        assert (tmp_path / "ledger.json").exists()
        assert (tmp_path / "accounts.json").exists()
        assert (tmp_path / "volumes").is_dir()

    def test_ledger_output_valid_json(self, tmp_path):
        runner.invoke(app, ["-o", str(tmp_path), "-v", "2", "--accounts", "2"])
        data = json.loads((tmp_path / "ledger.json").read_text())
        assert "ledger" in data
        assert "accountState" in data["ledger"]

    def test_validator_configs_created(self, tmp_path):
        result = runner.invoke(app, ["-o", str(tmp_path), "-v", "3", "--accounts", "2"])
        assert result.exit_code == 0, result.output
        volumes = tmp_path / "volumes"
        # Should have val0, val1, val2, and rippled
        assert (volumes / "val0" / "rippled.cfg").exists()
        assert (volumes / "val1" / "rippled.cfg").exists()
        assert (volumes / "val2" / "rippled.cfg").exists()

    def test_compose_file_created(self, tmp_path):
        result = runner.invoke(app, ["-o", str(tmp_path), "-v", "2", "--accounts", "2"])
        assert result.exit_code == 0, result.output
        assert (tmp_path / "docker-compose.yml").exists()

    def test_with_trustline(self, tmp_path):
        result = runner.invoke(
            app,
            [
                "-o",
                str(tmp_path),
                "-v",
                "2",
                "--accounts",
                "3",
                "-t",
                "0:1:USD:1000000000",
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads((tmp_path / "ledger.json").read_text())
        state = data["ledger"]["accountState"]
        ripple_states = [o for o in state if o.get("LedgerEntryType") == "RippleState"]
        assert len(ripple_states) > 0

    def test_with_amm_pool(self, tmp_path):
        result = runner.invoke(
            app,
            [
                "-o",
                str(tmp_path),
                "-v",
                "2",
                "--accounts",
                "3",
                "-t",
                "0:1:USD:1000000000",
                "-a",
                "XRP:USD:0:1000000000000:1000000:500:0",
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads((tmp_path / "ledger.json").read_text())
        state = data["ledger"]["accountState"]
        amm_entries = [o for o in state if o.get("LedgerEntryType") == "AMM"]
        assert len(amm_entries) > 0

    def test_custom_fees(self, tmp_path):
        result = runner.invoke(
            app,
            [
                "-o",
                str(tmp_path),
                "-v",
                "2",
                "--accounts",
                "2",
                "--base-fee",
                "10",
                "--reserve-base",
                "1000000",
                "--reserve-inc",
                "500",
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads((tmp_path / "ledger.json").read_text())
        state = data["ledger"]["accountState"]
        fee = next(o for o in state if o.get("LedgerEntryType") == "FeeSettings")
        assert fee["BaseFeeDrops"] == 10
        assert fee["ReserveBaseDrops"] == 1_000_000
        assert fee["ReserveIncrementDrops"] == 500

    def test_step_messages_in_output(self, tmp_path):
        result = runner.invoke(app, ["-o", str(tmp_path), "-v", "2", "--accounts", "2"])
        assert "Step 1/3" in result.output
        assert "Step 2/3" in result.output
        assert "Step 3/3" in result.output

    def test_invalid_trustline_spec(self, tmp_path):
        result = runner.invoke(
            app,
            [
                "-o",
                str(tmp_path),
                "-v",
                "2",
                "--accounts",
                "2",
                "-t",
                "bad",
            ],
        )
        assert result.exit_code != 0
