from pathlib import Path
from generate_ledger.rippled_cfg import RippledConfigSpec

def test_build_includes_all_blocks(tmp_path: Path):
    tpl = tmp_path / "rippled.cfg"
    tpl.write_text("# base\n", encoding="utf-8")
    spec = RippledConfigSpec(num_validators=2, template_path=tpl, base_dir=tmp_path)

    res = spec.build()
    assert len(res.nodes) == 3  # val0, val1, rippled
    # validator has seed + voting
    v0 = next(n for n in res.nodes if n.name == "val0")
    assert "[validation_seed]" in v0.config_text
    assert "[voting]" in v0.config_text
    # non-validator lacks seed/voting but has validators
    rp = next(n for n in res.nodes if n.name == "rippled")
    assert "[validation_seed]" not in rp.config_text
    assert "[validators]" in rp.config_text
