"""Tests for the rippled config CLI (generate_ledger.cli.rippled_cfg)."""

from typer.testing import CliRunner

from generate_ledger.cli.rippled_cfg import _load_features, app

runner = CliRunner()


class TestLoadFeatures:
    def test_none_returns_none(self):
        assert _load_features(None) is None

    def test_release_returns_list(self):
        result = _load_features("release")
        assert isinstance(result, list)
        assert len(result) > 0
        # All entries should be strings (amendment names)
        assert all(isinstance(name, str) for name in result)

    def test_release_contains_known_amendment(self):
        result = _load_features("release")
        assert "FlowCross" in result


class TestRippledWriteCommand:
    def test_basic_write(self, tmp_path):
        result = runner.invoke(
            app,
            [
                "-b",
                str(tmp_path),
                "-v",
                "2",
            ],
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / "val0" / "rippled.cfg").exists()
        assert (tmp_path / "val1" / "rippled.cfg").exists()

    def test_with_features_from_release(self, tmp_path):
        result = runner.invoke(
            app,
            [
                "-b",
                str(tmp_path),
                "-v",
                "1",
                "--features-from",
                "release",
            ],
        )
        assert result.exit_code == 0, result.output
        cfg_text = (tmp_path / "val0" / "rippled.cfg").read_text()
        assert "[features]" in cfg_text

    def test_zero_validators(self, tmp_path):
        """With 0 validators, should still produce the non-validator node."""
        result = runner.invoke(
            app,
            [
                "-b",
                str(tmp_path),
                "-v",
                "0",
            ],
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / "rippled" / "rippled.cfg").exists()
