"""CLI tests for the 'ledger' command using Typer's test runner.

The CLI hierarchy is: app -> ledger (group) -> ledger (command),
so invocations need ["ledger", "ledger", ...].
"""
import json

from typer.testing import CliRunner

from generate_ledger.cli import app

runner = CliRunner()


class TestLedgerCliCommand:
    def test_basic_invocation(self, tmp_path):
        outdir = str(tmp_path / "out")
        result = runner.invoke(app, ["ledger", "ledger", "-n", "2", "-o", outdir])
        assert result.exit_code == 0, result.output

    def test_with_trustline_flag(self, tmp_path):
        outdir = str(tmp_path / "out")
        result = runner.invoke(app, [
            "ledger", "ledger", "-n", "2", "-o", outdir,
            "-t", "0:1:USD:1000000000",
        ])
        assert result.exit_code == 0, result.output

    def test_with_amm_flag(self, tmp_path):
        outdir = str(tmp_path / "out")
        result = runner.invoke(app, [
            "ledger", "ledger", "-n", "2", "-o", outdir,
            "-t", "0:1:USD:1000000000",
            "-a", "XRP:USD:0:1000000000000:1000000:500:0",
        ])
        assert result.exit_code == 0, result.output

    def test_invalid_trustline_format(self, tmp_path):
        outdir = str(tmp_path / "out")
        result = runner.invoke(app, [
            "ledger", "ledger", "-n", "2", "-o", outdir,
            "-t", "invalid",
        ])
        assert result.exit_code != 0

    def test_output_is_valid_json(self, tmp_path):
        outdir = tmp_path / "out"
        result = runner.invoke(app, ["ledger", "ledger", "-n", "2", "-o", str(outdir)])
        assert result.exit_code == 0, result.output
        ledger_file = outdir / "ledger.json"
        assert ledger_file.exists()
        data = json.loads(ledger_file.read_text())
        assert "ledger" in data
        assert "accountState" in data["ledger"]

    def test_combined_options(self, tmp_path):
        outdir = str(tmp_path / "out")
        result = runner.invoke(app, [
            "ledger", "ledger", "-n", "3", "-o", outdir,
            "--num-trustlines", "1",
            "--currencies", "USD",
            "-t", "0:1:USD:1000000000",
        ])
        assert result.exit_code == 0, result.output

    def test_gateways_adds_to_regular_accounts(self, tmp_path):
        """With -n 3 --gateways 2, total should be 5 accounts (3 regular + 2 gateways)."""
        outdir = tmp_path / "out"
        result = runner.invoke(app, [
            "ledger", "ledger", "-n", "3", "-o", str(outdir),
            "--gateways", "2",
            "--assets-per-gateway", "1",
            "--gateway-currencies", "USD",
        ])
        assert result.exit_code == 0, result.output
        data = json.loads((outdir / "ledger.json").read_text())
        state = data["ledger"]["accountState"]
        genesis = "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh"
        accts = [e for e in state if e.get("LedgerEntryType") == "AccountRoot" and e["Account"] != genesis]
        assert len(accts) == 5  # 3 regular + 2 gateways

    def test_custom_fees(self, tmp_path):
        outdir = tmp_path / "out"
        result = runner.invoke(app, [
            "ledger", "ledger", "-n", "2", "-o", str(outdir),
            "--base-fee", "10",
            "--reserve-base", "1000000",
            "--reserve-inc", "500",
        ])
        assert result.exit_code == 0, result.output
        data = json.loads((outdir / "ledger.json").read_text())
        state = data["ledger"]["accountState"]
        fee_entry = next(e for e in state if e.get("LedgerEntryType") == "FeeSettings")
        assert fee_entry["BaseFeeDrops"] == 10
        assert fee_entry["ReserveBaseDrops"] == 1_000_000
        assert fee_entry["ReserveIncrementDrops"] == 500
