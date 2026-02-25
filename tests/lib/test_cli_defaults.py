"""Tests for generate_ledger.cli_defaults."""


from generate_ledger.cli_defaults import (
    OptMeta,
    _normalize,
    defaults_leaf_from_cfg,
    merge_default_maps,
    nest_default_map,
    normalized_mapping,
)


class TestNormalize:
    def test_string_becomes_optmeta(self):
        result = _normalize({"foo": "bar_field"})
        assert result == {"foo": OptMeta(field="bar_field")}

    def test_optmeta_passthrough(self):
        meta = OptMeta(field="num_validators", aliases=["-v"])
        result = _normalize({"validators": meta})
        assert result["validators"] is meta

    def test_mixed_mapping(self):
        mapping = {
            "simple": "simple_field",
            "rich": OptMeta(field="rich_field", env="GL_RICH"),
        }
        result = _normalize(mapping)
        assert result["simple"]["field"] == "simple_field"
        assert result["rich"]["field"] == "rich_field"
        assert result["rich"]["env"] == "GL_RICH"


class TestDefaultsLeafFromCfg:
    def test_extracts_matching_fields(self):
        from generate_ledger.compose import ComposeConfig
        cfg = ComposeConfig()
        leaf = defaults_leaf_from_cfg(cfg, "compose-write")
        assert "validators" in leaf
        assert leaf["validators"] == cfg.num_validators

    def test_path_converted_to_str(self):
        from generate_ledger.compose import ComposeConfig
        cfg = ComposeConfig()
        leaf = defaults_leaf_from_cfg(cfg, "compose-write")
        # compose_yml is a Path on the model, should be str in the leaf
        assert isinstance(leaf["output_file"], str)

    def test_skips_missing_fields(self):
        """If a field in CLI_DEFAULTS doesn't exist on the model, it's skipped."""

        class FakeModel:
            num_validators = 5
            # validator_name is missing

        leaf = defaults_leaf_from_cfg(FakeModel(), "compose-write")
        assert "validators" in leaf
        assert "validator_name" not in leaf


class TestNestDefaultMap:
    def test_single_segment(self):
        result = nest_default_map(["compose"], {"validators": 5})
        assert result == {"compose": {"validators": 5}}

    def test_two_segments(self):
        result = nest_default_map(["compose", "write"], {"validators": 5})
        assert result == {"compose": {"write": {"validators": 5}}}

    def test_empty_leaf(self):
        result = nest_default_map(["a", "b"], {})
        assert result == {"a": {"b": {}}}


class TestMergeDefaultMaps:
    def test_disjoint_maps(self):
        result = merge_default_maps({"a": 1}, {"b": 2})
        assert result == {"a": 1, "b": 2}

    def test_overlapping_nested_dicts(self):
        m1 = {"x": {"a": 1}}
        m2 = {"x": {"b": 2}}
        result = merge_default_maps(m1, m2)
        assert result == {"x": {"a": 1, "b": 2}}

    def test_scalar_override(self):
        result = merge_default_maps({"a": 1}, {"a": 99})
        assert result == {"a": 99}


class TestNormalizedMapping:
    def test_returns_optmeta_dict(self):
        result = normalized_mapping("compose-write")
        for _key, meta in result.items():
            assert "field" in meta
