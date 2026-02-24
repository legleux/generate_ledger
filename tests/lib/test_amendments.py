"""Tests for gl.amendments — amendment loading and filtering."""
import pytest
from gl.amendments import (
    Amendment,
    _enabled_amendment_hashes,
    _get_amendments_from_file,
    get_amendments,
    get_enabled_amendment_hashes,
)


# ---------------------------------------------------------------------------
# Amendment dataclass
# ---------------------------------------------------------------------------
class TestAmendmentDataclass:
    def test_creation(self):
        a = Amendment(name="Test", index="AB" * 32, enabled=True)
        assert a.name == "Test"
        assert a.enabled is True

    def test_frozen(self):
        a = Amendment(name="Test", index="AB" * 32, enabled=True)
        with pytest.raises(AttributeError):
            a.name = "Changed"

    def test_defaults(self):
        a = Amendment(name="Test", index="AB" * 32, enabled=False)
        assert a.obsolete is False


# ---------------------------------------------------------------------------
# _get_amendments_from_file
# ---------------------------------------------------------------------------
class TestGetAmendmentsFromFile:
    def test_load_default(self):
        data = _get_amendments_from_file()
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_load_explicit_path(self):
        from gl.amendments import DEFAULT_AMENDMENT_LIST
        data = _get_amendments_from_file(str(DEFAULT_AMENDMENT_LIST))
        assert isinstance(data, dict)

    def test_nonexistent_raises(self):
        with pytest.raises(Exception):
            _get_amendments_from_file("/nonexistent/path.json")


# ---------------------------------------------------------------------------
# get_enabled_amendment_hashes
# ---------------------------------------------------------------------------
class TestGetEnabledAmendmentHashes:
    def test_returns_list_of_hex_strings(self):
        hashes = get_enabled_amendment_hashes()
        assert isinstance(hashes, list)
        assert len(hashes) > 0
        for h in hashes:
            assert len(h) == 64
            assert all(c in "0123456789abcdefABCDEF" for c in h)

    def test_filter_helper(self):
        amendments = [
            Amendment(name="Enabled", index="AA" * 32, enabled=True),
            Amendment(name="Disabled", index="BB" * 32, enabled=False),
            Amendment(name="AlsoEnabled", index="CC" * 32, enabled=True),
        ]
        result = _enabled_amendment_hashes(amendments)
        assert len(result) == 2
        assert "AA" * 32 in result
        assert "CC" * 32 in result
        assert "BB" * 32 not in result
