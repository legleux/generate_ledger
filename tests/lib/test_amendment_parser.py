"""Tests for amendment hash computation, features.macro parsing, and profiles."""

import json
import pytest
from pathlib import Path

from gl.amendments import (
    Amendment,
    AmendmentProfile,
    amendment_hash,
    apply_develop_profile,
    get_amendments_for_profile,
    get_enabled_amendment_hashes,
    parse_features_macro,
    _apply_overrides,
    _load_amendments_from_json,
    DEFAULT_RELEASE_LIST,
)


# ---------------------------------------------------------------------------
# amendment_hash()
# ---------------------------------------------------------------------------
class TestAmendmentHash:
    def test_amm_hash_matches_known(self):
        """AMM hash should match the known value from rippled."""
        expected = "8CC0774A3BF66D1D22E76BBDA8E8A232E6B6313834301B3B23E8601196AE6455"
        assert amendment_hash("AMM") == expected

    def test_fix_prefix_applied_by_caller(self):
        """amendment_hash() hashes the exact string passed to it.
        The 'fix' prefix is added by _derive_name(), not amendment_hash()."""
        h = amendment_hash("fixAMMOverflowOffer")
        assert len(h) == 64
        assert all(c in "0123456789ABCDEF" for c in h)
        # Must differ from hashing without prefix
        assert h != amendment_hash("AMMOverflowOffer")

    def test_deterministic(self):
        assert amendment_hash("DID") == amendment_hash("DID")

    def test_different_names_different_hashes(self):
        assert amendment_hash("AMM") != amendment_hash("DID")

    def test_uppercase_hex(self):
        h = amendment_hash("SomeAmendment")
        assert h == h.upper()

    def test_length_is_64(self):
        assert len(amendment_hash("Test")) == 64


# ---------------------------------------------------------------------------
# parse_features_macro()
# ---------------------------------------------------------------------------
class TestParseFeaturesMacro:
    @pytest.fixture
    def macro_path(self, data_dir: Path) -> Path:
        return data_dir / "features_test.macro"

    def test_parses_active_features(self, macro_path):
        amendments = parse_features_macro(macro_path)
        names = {a.name for a in amendments}
        assert "AMM" in names
        assert "Clawback" in names
        assert "DID" in names
        assert "MPTokensV1" in names

    def test_parses_active_fixes_with_prefix(self, macro_path):
        amendments = parse_features_macro(macro_path)
        names = {a.name for a in amendments}
        assert "fixAMMOverflowOffer" in names
        assert "fixInnerObjTemplate2" in names
        # Raw names should NOT appear
        assert "AMMOverflowOffer" not in names
        assert "InnerObjTemplate2" not in names

    def test_parses_retired(self, macro_path):
        amendments = parse_features_macro(macro_path)
        by_name = {a.name: a for a in amendments}
        assert "MultiSign" in by_name
        assert by_name["MultiSign"].retired is True
        assert "fix1368" in by_name
        assert by_name["fix1368"].retired is True

    def test_parses_obsolete(self, macro_path):
        amendments = parse_features_macro(macro_path)
        by_name = {a.name: a for a in amendments}
        assert "CryptoConditionsSuite" in by_name
        assert by_name["CryptoConditionsSuite"].vote_behavior == "Obsolete"
        assert by_name["CryptoConditionsSuite"].supported is True
        assert by_name["CryptoConditionsSuite"].retired is False

    def test_total_count(self, macro_path):
        amendments = parse_features_macro(macro_path)
        # 4 features + 2 fixes + 1 obsolete + 2 retired = 9
        assert len(amendments) == 9

    def test_all_start_disabled(self, macro_path):
        amendments = parse_features_macro(macro_path)
        for a in amendments:
            assert a.enabled is False

    def test_supported_flag(self, macro_path):
        amendments = parse_features_macro(macro_path)
        by_name = {a.name: a for a in amendments}
        assert by_name["AMM"].supported is True
        assert by_name["MPTokensV1"].supported is False

    def test_vote_behavior(self, macro_path):
        amendments = parse_features_macro(macro_path)
        by_name = {a.name: a for a in amendments}
        assert by_name["AMM"].vote_behavior == "DefaultYes"
        assert by_name["Clawback"].vote_behavior == "DefaultNo"
        assert by_name["CryptoConditionsSuite"].vote_behavior == "Obsolete"

    def test_hash_matches_name(self, macro_path):
        """Each parsed amendment's index should match amendment_hash(name)."""
        amendments = parse_features_macro(macro_path)
        for a in amendments:
            assert a.index == amendment_hash(a.name)


# ---------------------------------------------------------------------------
# apply_develop_profile()
# ---------------------------------------------------------------------------
class TestApplyDevelopProfile:
    @pytest.fixture
    def macro_path(self, data_dir: Path) -> Path:
        return data_dir / "features_test.macro"

    def test_enables_defaultyes_supported(self, macro_path):
        raw = parse_features_macro(macro_path)
        profiled = apply_develop_profile(raw)
        by_name = {a.name: a for a in profiled}
        # AMM: Supported::yes, DefaultYes -> enabled
        assert by_name["AMM"].enabled is True
        # DID: Supported::yes, DefaultYes -> enabled
        assert by_name["DID"].enabled is True

    def test_enables_defaultno_if_supported(self, macro_path):
        raw = parse_features_macro(macro_path)
        profiled = apply_develop_profile(raw)
        by_name = {a.name: a for a in profiled}
        # Clawback: Supported::yes, DefaultNo -> enabled (Supported::yes is sufficient)
        assert by_name["Clawback"].enabled is True
        # fixInnerObjTemplate2: Supported::yes, DefaultNo -> enabled
        assert by_name["fixInnerObjTemplate2"].enabled is True

    def test_disables_unsupported(self, macro_path):
        raw = parse_features_macro(macro_path)
        profiled = apply_develop_profile(raw)
        by_name = {a.name: a for a in profiled}
        # MPTokensV1: Supported::no -> disabled
        assert by_name["MPTokensV1"].enabled is False

    def test_disables_obsolete(self, macro_path):
        raw = parse_features_macro(macro_path)
        profiled = apply_develop_profile(raw)
        by_name = {a.name: a for a in profiled}
        # CryptoConditionsSuite: Supported::yes, Obsolete -> disabled
        assert by_name["CryptoConditionsSuite"].enabled is False

    def test_enables_retired(self, macro_path):
        raw = parse_features_macro(macro_path)
        profiled = apply_develop_profile(raw)
        by_name = {a.name: a for a in profiled}
        # Retired amendments should be enabled
        assert by_name["MultiSign"].enabled is True
        assert by_name["fix1368"].enabled is True


# ---------------------------------------------------------------------------
# get_amendments_for_profile()
# ---------------------------------------------------------------------------
class TestGetAmendmentsForProfile:
    @pytest.fixture
    def macro_path(self, data_dir: Path) -> Path:
        return data_dir / "features_test.macro"

    def test_release_profile(self):
        amendments = get_amendments_for_profile(AmendmentProfile.RELEASE)
        assert len(amendments) > 0
        for a in amendments:
            if a.obsolete or not a.supported:
                assert a.enabled is False, f"{a.name} is obsolete/unsupported and should be disabled"
            else:
                assert a.enabled is True, f"{a.name} should be enabled in release profile"

    def test_develop_profile(self, macro_path):
        amendments = get_amendments_for_profile(
            AmendmentProfile.DEVELOP, source=macro_path
        )
        assert len(amendments) == 9
        enabled = [a for a in amendments if a.enabled]
        assert len(enabled) > 0

    def test_develop_without_source_raises(self):
        with pytest.raises(ValueError, match="features.macro"):
            get_amendments_for_profile(AmendmentProfile.DEVELOP)

    def test_custom_without_source_raises(self):
        with pytest.raises(ValueError, match="JSON file"):
            get_amendments_for_profile(AmendmentProfile.CUSTOM)

    def test_custom_profile(self):
        amendments = get_amendments_for_profile(
            AmendmentProfile.CUSTOM, source=str(DEFAULT_RELEASE_LIST)
        )
        assert len(amendments) > 0

    def test_string_profile(self, macro_path):
        """Profiles can be passed as plain strings."""
        amendments = get_amendments_for_profile("develop", source=macro_path)
        assert len(amendments) == 9

    def test_enable_override(self, macro_path):
        amendments = get_amendments_for_profile(
            AmendmentProfile.DEVELOP,
            source=macro_path,
            enable=["MPTokensV1"],
        )
        by_name = {a.name: a for a in amendments}
        # MPTokensV1 is Supported::no, so develop would disable it
        # but explicit enable should override
        assert by_name["MPTokensV1"].enabled is True

    def test_disable_override(self, macro_path):
        amendments = get_amendments_for_profile(
            AmendmentProfile.DEVELOP,
            source=macro_path,
            disable=["AMM"],
        )
        by_name = {a.name: a for a in amendments}
        # AMM would be enabled by develop profile, but disable overrides
        assert by_name["AMM"].enabled is False


# ---------------------------------------------------------------------------
# get_enabled_amendment_hashes() — profile path
# ---------------------------------------------------------------------------
class TestGetEnabledAmendmentHashesProfile:
    def test_release_profile(self):
        hashes = get_enabled_amendment_hashes(profile="release")
        assert len(hashes) > 0
        for h in hashes:
            assert len(h) == 64

    def test_develop_profile(self, data_dir):
        macro_path = data_dir / "features_test.macro"
        hashes = get_enabled_amendment_hashes(
            profile="develop",
            amendment_source=str(macro_path),
        )
        assert len(hashes) > 0

    def test_legacy_fallback(self):
        """When profile=None, uses the legacy source parameter."""
        hashes = get_enabled_amendment_hashes()
        assert len(hashes) > 0


# ---------------------------------------------------------------------------
# _apply_overrides()
# ---------------------------------------------------------------------------
class TestApplyOverrides:
    def test_enable_disabled_amendment(self):
        amendments = [
            Amendment(name="Foo", index="AA" * 32, enabled=False),
            Amendment(name="Bar", index="BB" * 32, enabled=True),
        ]
        result = _apply_overrides(amendments, enable={"Foo"}, disable=set())
        by_name = {a.name: a for a in result}
        assert by_name["Foo"].enabled is True
        assert by_name["Bar"].enabled is True

    def test_disable_enabled_amendment(self):
        amendments = [
            Amendment(name="Foo", index="AA" * 32, enabled=True),
            Amendment(name="Bar", index="BB" * 32, enabled=True),
        ]
        result = _apply_overrides(amendments, enable=set(), disable={"Foo"})
        by_name = {a.name: a for a in result}
        assert by_name["Foo"].enabled is False
        assert by_name["Bar"].enabled is True


# ---------------------------------------------------------------------------
# Release JSON integrity
# ---------------------------------------------------------------------------
class TestReleaseJson:
    def test_file_exists(self):
        assert DEFAULT_RELEASE_LIST.is_file() or Path(str(DEFAULT_RELEASE_LIST)).exists()

    def test_loadable(self):
        amendments = _load_amendments_from_json(Path(str(DEFAULT_RELEASE_LIST)))
        assert len(amendments) > 0

    def test_all_enabled(self):
        amendments = _load_amendments_from_json(Path(str(DEFAULT_RELEASE_LIST)))
        for a in amendments:
            if a.obsolete or not a.supported:
                assert a.enabled is False, f"{a.name} is obsolete/unsupported and should be disabled"
            else:
                assert a.enabled is True, f"{a.name} should be enabled in release JSON"

    def test_retired_count(self):
        amendments = _load_amendments_from_json(Path(str(DEFAULT_RELEASE_LIST)))
        retired = [a for a in amendments if a.retired]
        assert len(retired) == 15

    def test_obsolete_count(self):
        amendments = _load_amendments_from_json(Path(str(DEFAULT_RELEASE_LIST)))
        obsolete = [a for a in amendments if a.obsolete]
        assert len(obsolete) == 4

    def test_total_count(self):
        amendments = _load_amendments_from_json(Path(str(DEFAULT_RELEASE_LIST)))
        assert len(amendments) == 92
