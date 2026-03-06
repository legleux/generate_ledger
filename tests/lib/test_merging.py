"""Tests for generate_ledger.utils.merging.deep_merge."""

from generate_ledger.utils.merging import deep_merge


class TestDeepMerge:
    def test_flat_merge(self):
        base = {"a": 1, "b": 2}
        result = deep_merge(base, {"c": 3})
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_nested_merge(self):
        base = {"x": {"a": 1, "b": 2}}
        result = deep_merge(base, {"x": {"c": 3}})
        assert result == {"x": {"a": 1, "b": 2, "c": 3}}

    def test_scalar_override(self):
        base = {"a": 1}
        result = deep_merge(base, {"a": 99})
        assert result == {"a": 99}

    def test_dict_over_scalar(self):
        base = {"a": 1}
        result = deep_merge(base, {"a": {"nested": True}})
        assert result == {"a": {"nested": True}}

    def test_empty_override(self):
        base = {"a": 1}
        result = deep_merge(base, {})
        assert result == {"a": 1}

    def test_mutates_base(self):
        """deep_merge mutates and returns the base dict."""
        base = {"a": 1}
        result = deep_merge(base, {"b": 2})
        assert result is base
