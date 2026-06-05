"""Compute the next release tag from the latest tag and a bump level.

Pure computation lives in compute_next_version(); the CLI reads the latest tag
from git and prints the next tag (and a GITHUB_OUTPUT line when available).
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass

BUMP_LEVELS = ("patch", "minor", "major", "rc", "beta", "hotfix")
PRERELEASE_CHANNELS = {"beta", "rc"}

_TAG_RE = re.compile(
    r"^v(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<semver_channel>beta|rc)\.(?P<semver_number>[1-9]\d*)"
    r"|\.post(?P<post_number>[1-9]\d*))?$"
)


@dataclass(frozen=True)
class _Parsed:
    """Parsed supported release tag; channel and number are None for stable tags."""

    major: int
    minor: int
    patch: int
    channel: str | None
    number: int | None


def _parse(tag: str) -> _Parsed:
    match = _TAG_RE.fullmatch(tag.strip())
    if match is None:
        raise ValueError(f"Cannot parse latest tag {tag!r}; expected vX.Y.Z, vX.Y.Z-(beta|rc).N, or vX.Y.Z.postN")

    channel = match.group("semver_channel")
    number = match.group("semver_number")
    post_number = match.group("post_number")
    if post_number is not None:
        channel = "hotfix"
        number = post_number

    return _Parsed(
        major=int(match.group("major")),
        minor=int(match.group("minor")),
        patch=int(match.group("patch")),
        channel=channel,
        number=int(number) if number else None,
    )


def _compute_stable_bump(parsed: _Parsed, bump: str) -> str:
    """Handle patch/minor/major bumps, including finalizing a prerelease."""
    if parsed.channel in PRERELEASE_CHANNELS and bump == "patch":
        # Finalizing an existing prerelease of X.Y.Z with "patch" yields X.Y.Z itself.
        return f"v{parsed.major}.{parsed.minor}.{parsed.patch}"
    if bump == "patch":
        return f"v{parsed.major}.{parsed.minor}.{parsed.patch + 1}"
    if bump == "minor":
        return f"v{parsed.major}.{parsed.minor + 1}.0"
    return f"v{parsed.major + 1}.0.0"


def _compute_prerelease_bump(parsed: _Parsed, bump: str) -> str:
    """Handle rc/beta bumps."""
    if parsed.channel == bump:
        assert parsed.number is not None
        return f"v{parsed.major}.{parsed.minor}.{parsed.patch}-{bump}.{parsed.number + 1}"
    if parsed.channel in PRERELEASE_CHANNELS:
        # different prerelease channel on the same base: restart numbering
        return f"v{parsed.major}.{parsed.minor}.{parsed.patch}-{bump}.1"
    # latest is stable or post-release: prerelease of the next patch
    return f"v{parsed.major}.{parsed.minor}.{parsed.patch + 1}-{bump}.1"


def _compute_hotfix_bump(parsed: _Parsed) -> str:
    """Handle PEP 440 post-release hotfix bumps."""
    if parsed.channel in PRERELEASE_CHANNELS:
        raise ValueError("Cannot compute a hotfix from a prerelease tag; finalize the release first")
    if parsed.channel == "hotfix":
        assert parsed.number is not None
        return f"v{parsed.major}.{parsed.minor}.{parsed.patch}.post{parsed.number + 1}"
    return f"v{parsed.major}.{parsed.minor}.{parsed.patch}.post1"


def compute_next_version(latest: str | None, bump: str) -> str:
    if bump not in BUMP_LEVELS:
        raise ValueError(f"Unknown bump {bump!r}; expected one of {', '.join(BUMP_LEVELS)}")

    if latest is None:
        base = {"patch": (0, 0, 1), "minor": (0, 1, 0), "major": (1, 0, 0)}
        if bump in ("patch", "minor", "major"):
            major, minor, patch = base[bump]
            return f"v{major}.{minor}.{patch}"
        if bump == "hotfix":
            raise ValueError("Cannot compute a hotfix without an existing stable release tag")
        return f"v0.0.1-{bump}.1"

    parsed = _parse(latest)
    if bump in ("patch", "minor", "major"):
        return _compute_stable_bump(parsed, bump)
    if bump == "hotfix":
        return _compute_hotfix_bump(parsed)
    return _compute_prerelease_bump(parsed, bump)


def _latest_tag() -> str | None:
    try:
        # version:refname sorts stable tags above same-base prereleases (RPM-style); the regex below is the real gate.
        out = subprocess.run(
            ["git", "tag", "--list", "v*", "--sort=-version:refname"],
            capture_output=True,
            text=True,
            check=True,
        )
    except OSError:
        return None  # git not available; treat as no tags
    except subprocess.CalledProcessError as exc:
        print(f"::warning::git tag listing failed: {(exc.stderr or '').strip()}", file=sys.stderr)
        return None
    for line in out.stdout.splitlines():
        candidate = line.strip()
        if _TAG_RE.fullmatch(candidate):
            return candidate
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bump", choices=BUMP_LEVELS)
    parser.add_argument("--latest", default=None, help="Override the latest tag (default: read from git)")
    args = parser.parse_args(argv)

    latest = args.latest if args.latest is not None else _latest_tag()
    try:
        next_tag = compute_next_version(latest, args.bump)
    except ValueError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 2

    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write(f"tag={next_tag}\n")
            handle.write(f"version={next_tag.removeprefix('v')}\n")
    print(next_tag)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
