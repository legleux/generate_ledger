#!/usr/bin/env python3
"""Generate a minimal test fixture from a real rippled features.macro.

Selects one representative amendment for each distinct
(macro_type, supported, vote_behavior) combination, producing a compact
fixture that covers all parser code paths.

Usage:
    python scripts/update_test_fixture.py PATH_TO_FEATURES_MACRO

    # Or auto-detect from sibling rippled checkouts:
    python scripts/update_test_fixture.py

Output is written to tests/data/features_test.macro.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
FIXTURE_PATH = PROJECT_ROOT / "tests" / "data" / "features_test.macro"

# ---------------------------------------------------------------------------
# Parse raw macro lines (intentionally independent of gl.amendments so the
# script can validate the parser rather than depend on it)
# ---------------------------------------------------------------------------

_RE_ACTIVE = re.compile(
    r"(XRPL_(FEATURE|FIX))\s*\(\s*(\w+)\s*,"
    r"\s*Supported::(yes|no)\s*,"
    r"\s*VoteBehavior::(\w+)\s*\)"
)

_RE_RETIRE = re.compile(r"(XRPL_RETIRE)\s*\(\s*(\w+)\s*\)")


def _parse_lines(text: str) -> list[dict]:
    entries = []
    for m in _RE_ACTIVE.finditer(text):
        macro, kind, name, supported, vote = m.groups()
        entries.append(
            {
                "macro": macro,
                "kind": kind,
                "name": name,
                "supported": supported,
                "vote": vote,
                "line": m.group(0),
            }
        )
    for m in _RE_RETIRE.finditer(text):
        macro, name = m.groups()
        entries.append(
            {
                "macro": macro,
                "kind": "RETIRE",
                "name": name,
                "supported": None,
                "vote": None,
                "line": m.group(0),
            }
        )
    return entries


def _bucket_key(e: dict) -> tuple:
    return (e["macro"], e["supported"], e["vote"])


# ---------------------------------------------------------------------------
# Find a real features.macro
# ---------------------------------------------------------------------------


def _find_real_macro(explicit: str | None = None) -> Path | None:
    if explicit:
        p = Path(explicit)
        if p.is_file():
            return p
        print(f"ERROR: {p} is not a file", file=sys.stderr)
        sys.exit(1)

    ripple_root = PROJECT_ROOT.parent  # ~/dev/Ripple/
    for glob in [
        "*/include/xrpl/protocol/detail/features.macro",
        "*/*/include/xrpl/protocol/detail/features.macro",
    ]:
        for candidate in sorted(
            ripple_root.glob(glob),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            return candidate
    return None


# ---------------------------------------------------------------------------
# Generate fixture
# ---------------------------------------------------------------------------


def generate_fixture(source: Path) -> str:
    text = source.read_text()
    entries = _parse_lines(text)

    # Select one representative per bucket
    seen: dict[tuple, dict] = {}
    for e in entries:
        key = _bucket_key(e)
        if key not in seen:
            seen[key] = e

    # Group by category for readability
    active_features = [e for e in seen.values() if e["macro"] == "XRPL_FEATURE" and e["vote"] not in ("Obsolete",)]
    active_fixes = [e for e in seen.values() if e["macro"] == "XRPL_FIX" and e["vote"] not in ("Obsolete",)]
    obsolete = [e for e in seen.values() if e["vote"] == "Obsolete"]
    retired = [e for e in seen.values() if e["kind"] == "RETIRE"]

    lines = [
        "// Minimal features.macro fixture for testing parse_features_macro()",
        f"// Auto-generated from: {source.name}",
        f"// Source: {source}",
        "",
    ]

    if active_features:
        lines.append("// Active features")
        for e in active_features:
            name_comma = e["name"] + ","
            lines.append(f"XRPL_FEATURE({name_comma:<25s}Supported::{e['supported']},  VoteBehavior::{e['vote']})")
        lines.append("")

    if active_fixes:
        lines.append('// Active fixes (get "fix" prefix)')
        for e in active_fixes:
            name_comma = e["name"] + ","
            lines.append(f"XRPL_FIX({name_comma:<29s}Supported::{e['supported']},  VoteBehavior::{e['vote']})")
        lines.append("")

    if obsolete:
        lines.append("// Obsolete (supported but never activated on mainnet)")
        for e in obsolete:
            name_comma = e["name"] + ","
            macro = e["macro"]
            pad = 25 if macro == "XRPL_FEATURE" else 29
            lines.append(f"{macro}({name_comma:<{pad}s}Supported::{e['supported']},  VoteBehavior::{e['vote']})")
        lines.append("")

    if retired:
        lines.append("// Retired amendments (active for years, pre-amendment code removed)")
        for e in retired:
            lines.append(f"XRPL_RETIRE({e['name']})")
        lines.append("")

    return "\n".join(lines)


def main():
    explicit = sys.argv[1] if len(sys.argv) > 1 else None
    source = _find_real_macro(explicit)

    if source is None:
        print(
            "ERROR: No features.macro found. Provide a path as argument or clone rippled in a sibling directory.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Source: {source}")

    fixture = generate_fixture(source)

    # Show what will be written
    print(f"\n--- {FIXTURE_PATH.relative_to(PROJECT_ROOT)} ---")
    print(fixture)
    print("---")

    # Count entries
    entry_count = sum(1 for line in fixture.splitlines() if line.startswith("XRPL_"))
    print(f"\n{entry_count} representative amendments (one per macro/supported/vote bucket)")

    # Confirm
    resp = input(f"\nWrite to {FIXTURE_PATH}? [Y/n] ").strip().lower()
    if resp in ("", "y", "yes"):
        FIXTURE_PATH.write_text(fixture)
        print(f"Written to {FIXTURE_PATH}")
        print("\nNext steps:")
        print("  1. Review test assertions in tests/lib/test_amendment_parser.py")
        print("  2. Run: pytest tests/lib/test_amendment_parser.py -v")
    else:
        print("Aborted.")


if __name__ == "__main__":
    main()
