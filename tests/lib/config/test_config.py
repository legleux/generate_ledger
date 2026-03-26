from pathlib import Path

from generate_ledger.xrpld_cfg import XrpldConfigSpec


def test_build_includes_all_blocks(tmp_path: Path):
    tpl = tmp_path / "xrpld.cfg"
    tpl.write_text("# base\n", encoding="utf-8")
    spec = XrpldConfigSpec(num_validators=2, template_path=tpl, base_dir=tmp_path)

    res = spec.build()
    assert len(res.nodes) == 3  # val0, val1, xrpld
    # validator has seed + voting
    v0 = next(n for n in res.nodes if n.name == "val0")
    assert "[validation_seed]" in v0.config_text
    assert "[voting]" in v0.config_text
    # non-validator lacks seed/voting but has validators
    rp = next(n for n in res.nodes if n.name == "xrpld")
    assert "[validation_seed]" not in rp.config_text
    assert "[validators]" in rp.config_text


class TestLogLevel:
    """Tests for log_level parameter on XrpldConfigSpec."""

    def _build_with_log_level(self, tmp_path: Path, log_level: str):
        tpl = tmp_path / "xrpld.cfg"
        tpl.write_text('{ "command": "log_level", "severity": "info" }\n', encoding="utf-8")
        spec = XrpldConfigSpec(num_validators=1, template_path=tpl, base_dir=tmp_path, log_level=log_level)
        return spec.build()

    def test_default_log_level_is_info(self, tmp_path: Path):
        res = self._build_with_log_level(tmp_path, "info")
        assert '"severity": "info"' in res.nodes[0].config_text

    def test_log_level_debug(self, tmp_path: Path):
        res = self._build_with_log_level(tmp_path, "debug")
        assert '"severity": "debug"' in res.nodes[0].config_text
        assert '"severity": "info"' not in res.nodes[0].config_text

    def test_log_level_trace(self, tmp_path: Path):
        res = self._build_with_log_level(tmp_path, "trace")
        assert '"severity": "trace"' in res.nodes[0].config_text

    def test_log_level_applied_to_all_nodes(self, tmp_path: Path):
        tpl = tmp_path / "xrpld.cfg"
        tpl.write_text('{ "command": "log_level", "severity": "info" }\n', encoding="utf-8")
        spec = XrpldConfigSpec(num_validators=2, template_path=tpl, base_dir=tmp_path, log_level="warning")
        res = spec.build()
        for node in res.nodes:
            assert '"severity": "warning"' in node.config_text

    def test_invalid_log_level_raises(self, tmp_path: Path):
        tpl = tmp_path / "xrpld.cfg"
        tpl.write_text("# base\n", encoding="utf-8")
        spec = XrpldConfigSpec(num_validators=1, template_path=tpl, base_dir=tmp_path, log_level="verbose")
        import pytest

        with pytest.raises(ValueError, match="log_level must be one of"):
            spec.build()
