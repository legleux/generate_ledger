from pathlib import Path

import pytest
from click.testing import CliRunner

from generate_ledger import __app_name__
from generate_ledger.cli.main import cli as app

runner = CliRunner()


@pytest.mark.skip(reason="config command not implemented yet")
def test_cli_config_help():
    r = runner.invoke(app, ["config", "--help"], prog_name=__app_name__)
    assert r.exit_code == 0, r.output
    assert __app_name__ in r.output
    assert "config" in r.output


def test_rippled_write(tmp_path: Path):
    tpl = tmp_path / "rippled.cfg"
    tpl.write_text("# base template\n", encoding="utf-8")

    outdir = tmp_path / "vols"
    r = runner.invoke(
        app,
        [
            "rippled",
            "--template-path",
            str(tpl),
            "--base-dir",
            str(outdir),
            "--validators",
            "3",
            "--keygen",
            "xrpl",
        ],
        prog_name=__app_name__,
    )
    assert r.exit_code == 0, r.output

    # 3 validators + 1 non-validator
    for name in ("val0", "val1", "val2", "rippled"):
        cfg = outdir / name / "rippled.cfg"
        assert cfg.exists(), f"missing {cfg}"
