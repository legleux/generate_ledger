"""Integration test: validate parser against a real rippled features.macro.

Skipped when no real features.macro is available.  Set the env var
``FEATURES_MACRO_PATH`` to point at the file explicitly, or let the test
search well-known sibling directories under ``~/dev/Ripple/``.
"""

import os
import re
from pathlib import Path

import pytest

from gl.amendments import parse_features_macro, amendment_hash

# ---------------------------------------------------------------------------
# Locate the real features.macro
# ---------------------------------------------------------------------------

_SEARCH_GLOBS = [
    # Relative to the repo root's grandparent (~/dev/Ripple/)
    "*/include/xrpl/protocol/detail/features.macro",
    "*/*/include/xrpl/protocol/detail/features.macro",
]


def _find_real_macro() -> Path | None:
    explicit = os.environ.get("FEATURES_MACRO_PATH")
    if explicit:
        p = Path(explicit)
        return p if p.is_file() else None

    # Search sibling repos under ~/dev/Ripple/
    ripple_root = Path(__file__).resolve().parents[3]  # …/generate_ledger -> ~/dev/Ripple
    for glob in _SEARCH_GLOBS:
        for candidate in sorted(ripple_root.glob(glob), key=lambda p: p.stat().st_mtime, reverse=True):
            return candidate
    return None


_real_macro = _find_real_macro()

pytestmark = pytest.mark.skipif(
    _real_macro is None,
    reason="No real features.macro found (set FEATURES_MACRO_PATH or clone rippled nearby)",
)


# Regex that matches ANY XRPL_ macro line (for detecting unrecognized patterns)
_RE_ANY_MACRO = re.compile(r"^\s*(XRPL_\w+)\s*\(", re.MULTILINE)

# Patterns our parser is expected to handle
_KNOWN_MACROS = {"XRPL_FEATURE", "XRPL_FIX", "XRPL_RETIRE", "XRPL_RETIRE_FEATURE", "XRPL_RETIRE_FIX"}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRealFeaturesMacro:
    def test_parser_does_not_crash(self):
        amendments = parse_features_macro(_real_macro)
        assert len(amendments) > 0

    def test_all_have_valid_hashes(self):
        amendments = parse_features_macro(_real_macro)
        for a in amendments:
            assert len(a.index) == 64
            assert a.index == amendment_hash(a.name)

    def test_no_unrecognized_macros(self):
        """Every XRPL_* macro line in the file should be a pattern we handle."""
        text = _real_macro.read_text()
        found_macros = set(_RE_ANY_MACRO.findall(text))
        unknown = found_macros - _KNOWN_MACROS
        assert not unknown, (
            f"Unrecognized macro(s) in {_real_macro.name}: {unknown}. "
            f"Update the parser in amendments.py and the test fixture."
        )

    def test_no_amendments_silently_dropped(self):
        """The number of parsed amendments should match the number of macro invocations."""
        text = _real_macro.read_text()
        macro_count = len(_RE_ANY_MACRO.findall(text))
        amendments = parse_features_macro(_real_macro)
        assert len(amendments) == macro_count, (
            f"Parser returned {len(amendments)} amendments but file has "
            f"{macro_count} macro invocations — some were silently dropped."
        )

    def test_has_expected_categories(self):
        """Real file should contain a mix of categories our test fixture covers."""
        amendments = parse_features_macro(_real_macro)
        behaviors = {a.vote_behavior for a in amendments}
        # At minimum we expect DefaultYes and DefaultNo
        assert "DefaultYes" in behaviors
        assert "DefaultNo" in behaviors

    def test_retired_amendments_present(self):
        """Real file should have at least some retired amendments."""
        amendments = parse_features_macro(_real_macro)
        retired = [a for a in amendments if a.retired]
        assert len(retired) > 0, "Expected at least one retired amendment"

    def test_source_path(self):
        """Report which file was used (visible in pytest -v output)."""
        assert _real_macro.is_file(), f"Using: {_real_macro}"
