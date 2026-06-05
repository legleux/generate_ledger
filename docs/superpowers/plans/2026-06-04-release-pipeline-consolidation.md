# Release Pipeline Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace two competing stubbed `Release` workflows with a single tag-driven pipeline that builds and publishes the package to PyPI/TestPyPI via uv trusted publishing, with versions derived dynamically from git tags and releases initiated through an action-driven, PR-reviewed bump.

**Architecture:** Approach A from the spec — the git tag is the single source of truth. `uv-dynamic-versioning` (a hatchling version plugin) feeds the tag into `uv build`; nothing carries a hardcoded version. A `release-prep.yml` workflow computes the next version, opens a changelog-only PR, and on merge pushes the tag with a PAT, which triggers `release.yml` to build, test, publish (trusted publishing), and create the GitHub Release. GitHub Environments (`release`/`prerelease`) scope the trusted publisher and gate prod behind required reviewers.

**Tech Stack:** Python 3.12+, uv, hatchling, uv-dynamic-versioning, git-cliff, GitHub Actions, pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-06-04-release-pipeline-consolidation-design.md`

---

## File Structure

| Action | Path                                        | Responsibility                                                                   |
| ------ | ------------------------------------------- | -------------------------------------------------------------------------------- |
| Modify | `pyproject.toml`                            | Dynamic version via hatchling + uv-dynamic-versioning; TestPyPI index definition |
| Delete | `.github/workflows/publish.yml`             | Older duplicate Release workflow                                                 |
| Delete | `scripts/release_automation.py`             | Helper for the deleted workflow                                                  |
| Delete | `tests/scripts/test_release_automation.py`  | Tests the deleted module                                                         |
| Delete | `scripts/release/stub_build.py`             | Stub build, replaced by `uv build`                                               |
| Modify | `.github/workflows/release.yml`             | Single Release workflow: real build + test gate + trusted publish                |
| Create | `scripts/release/next_version.py`           | Pure version-bump computation from latest tag                                    |
| Create | `tests/scripts/test_next_version.py`        | Tests for `next_version.py`                                                      |
| Create | `tests/scripts/test_parse_release_tag.py`   | Tests for the kept tag parser                                                    |
| Create | `tests/scripts/test_check_release_actor.py` | Tests for the kept authz script                                                  |
| Create | `cliff.toml`                                | git-cliff changelog config                                                       |
| Create | `.github/workflows/release-prep.yml`        | Bump → changelog PR → tag-on-merge                                               |
| Modify | `CHANGELOG.md`                              | git-cliff-compatible header (keep existing entries)                              |
| Modify | `docs/release.md`                           | Document the new flow + manual setup checklist                                   |
| Modify | `CLAUDE.md`                                 | Update CI section                                                                |

Keep (commit as-is, currently untracked): `scripts/release/parse_release_tag.py`, `scripts/release/check_release_actor.py`.

**Recommended commit grouping:** Tasks 1–9 each end in their own commit. Conventional-commit prefixes are required (the repo enforces them).

---

## Task 1: Switch packaging to dynamic versioning

**Files:**

- Modify: `pyproject.toml:1-36`

- [ ] **Step 1: Edit `[project]` to drop the hardcoded version**

Replace lines 1-3:

```toml
[project]
name = "generate-ledger"
version = "0.0.8"
```

with:

```toml
[project]
name = "generate-ledger"
dynamic = ["version"]
```

- [ ] **Step 2: Edit `[build-system]` to add the plugin**

Replace:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

with:

```toml
[build-system]
requires = ["hatchling", "uv-dynamic-versioning"]
build-backend = "hatchling.build"

[tool.hatch.version]
source = "uv-dynamic-versioning"

[tool.uv-dynamic-versioning]
vcs = "git"
style = "pep440"
# Used when git history/tags are unavailable (Dependabot, sdist-from-sdist, sandboxes).
fallback-version = "0.0.0"
```

- [ ] **Step 3: Add a TestPyPI publish index**

Append to the end of `pyproject.toml`:

```toml
[[tool.uv.index]]
name = "testpypi"
url = "https://test.pypi.org/simple/"
publish-url = "https://test.pypi.org/legacy/"
explicit = true
```

- [ ] **Step 4: Verify the build reads the version from a tag**

Run:

```bash
git tag v9.9.9-rc.1
uv build 2>&1 | tail -5
ls dist/
git tag -d v9.9.9-rc.1
```

Expected: `dist/` contains `generate_ledger-9.9.9rc1.tar.gz` and `generate_ledger-9.9.9rc1-py3-none-any.whl` (PEP 440 `9.9.9rc1`, proving the tag drove the version). Clean up: `rm -rf dist`.

- [ ] **Step 5: Verify a clean (no-tag) build falls back instead of failing**

Run:

```bash
uv build 2>&1 | tail -3 && ls dist/ && rm -rf dist
```

Expected: build succeeds using the dirty/last-tag-derived or `0.0.0` fallback version (no crash). The point is that the absence of an exact tag does not break the build.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml
git commit -m "build: derive version from git tags via uv-dynamic-versioning"
```

---

## Task 2: Characterization tests for `parse_release_tag.py`

The kept parser currently has no tests. Add tests that pin its existing behavior before anything depends on it.

**Files:**

- Create: `tests/scripts/test_parse_release_tag.py`

- [ ] **Step 1: Write the tests**

```python
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "release"))

from parse_release_tag import InvalidReleaseTag, parse_release_tag


@pytest.mark.parametrize(
    ("tag", "channel", "package_version", "prerelease", "publish_target", "release_environment"),
    [
        ("v1.2.3", "stable", "1.2.3", False, "pypi", "release"),
        ("v1.2.3-beta.1", "beta", "1.2.3b1", True, "testpypi", "prerelease"),
        ("v1.2.3-rc.2", "rc", "1.2.3rc2", True, "testpypi", "prerelease"),
        ("v1.2.3b1", "beta", "1.2.3b1", True, "testpypi", "prerelease"),
        ("v1.2.3rc1", "rc", "1.2.3rc1", True, "testpypi", "prerelease"),
        ("v1.2.4.post1", "hotfix", "1.2.4.post1", False, "pypi", "release"),
    ],
)
def test_parse_release_tag_classifies(tag, channel, package_version, prerelease, publish_target, release_environment):
    result = parse_release_tag(tag)
    assert result.tag == tag
    assert result.channel == channel
    assert result.package_version == package_version
    assert result.prerelease is prerelease
    assert result.publish_target == publish_target
    assert result.release_environment == release_environment


def test_parse_release_tag_strips_refs_prefix():
    result = parse_release_tag("refs/tags/v1.2.3")
    assert result.tag == "v1.2.3"
    assert result.version == "1.2.3"


@pytest.mark.parametrize("tag", ["1.2.3", "v1.2", "v1.2.3-alpha.1", "v01.2.3", "v1.2.3-rc"])
def test_parse_release_tag_rejects_unsupported(tag):
    with pytest.raises(InvalidReleaseTag):
        parse_release_tag(tag)


def test_as_github_outputs_stringifies_bools():
    outputs = parse_release_tag("v1.2.3-rc.1").as_github_outputs()
    assert outputs["prerelease"] == "true"
    assert outputs["channel"] == "rc"
    assert outputs["qualifier_number"] == "1"
```

- [ ] **Step 2: Run the tests**

Run: `uv run pytest tests/scripts/test_parse_release_tag.py -v --no-cov`
Expected: all PASS. If any case fails, the assertion encodes the _expected_ spec behavior — check the failure against `scripts/release/parse_release_tag.py` and fix the test to match the actual implemented classification (these are characterization tests; the implementation is the source of truth unless it is clearly wrong).

- [ ] **Step 3: Commit**

```bash
git add tests/scripts/test_parse_release_tag.py scripts/release/parse_release_tag.py
git commit -m "test: cover release tag parser"
```

---

## Task 3: Characterization tests for `check_release_actor.py`

**Files:**

- Create: `tests/scripts/test_check_release_actor.py`

- [ ] **Step 1: Write the tests**

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "release"))

from check_release_actor import is_actor_authorized, resolve_allowed_actors, split_actors


def test_split_actors_handles_commas_and_whitespace():
    assert split_actors("alice, bob\n charlie") == ("alice", "bob", "charlie")
    assert split_actors("") == ()
    assert split_actors(None) == ()


def test_resolve_allowed_actors_prefers_explicit_list():
    assert resolve_allowed_actors("alice,bob", "the-org") == ("alice", "bob")


def test_resolve_allowed_actors_falls_back_to_owner():
    assert resolve_allowed_actors("", "the-org") == ("the-org",)
    assert resolve_allowed_actors(None, None) == ()


def test_is_actor_authorized_is_case_insensitive():
    allowed = ("Alice", "Bob")
    assert is_actor_authorized("alice", allowed) is True
    assert is_actor_authorized("BOB", allowed) is True
    assert is_actor_authorized("mallory", allowed) is False


def test_is_actor_authorized_empty_allowlist_denies():
    assert is_actor_authorized("alice", ()) is False
```

- [ ] **Step 2: Run the tests**

Run: `uv run pytest tests/scripts/test_check_release_actor.py -v --no-cov`
Expected: all PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/scripts/test_check_release_actor.py scripts/release/check_release_actor.py
git commit -m "test: cover release actor authorization"
```

---

## Task 4: `next_version.py` — compute the next version from the latest tag (TDD)

This replaces `uv version --bump` (which needs a committed version). A pure function does the math; a thin CLI wraps git access so it is unit-testable without a repo.

**Bump policy (explicit):** given the latest tag's parsed version and a bump level:

- `patch` → `X.Y.(Z+1)` (stable)
- `minor` → `X.(Y+1).0` (stable)
- `major` → `(X+1).0.0` (stable)
- `rc` / `beta`:
  - if the latest tag is **stable** `vX.Y.Z` → start a prerelease of the next patch: `vX.Y.(Z+1)-rc.1` / `-beta.1`
  - if the latest tag is a prerelease of the **same channel** `vX.Y.Z-rc.N` → `vX.Y.Z-rc.(N+1)`
  - if the latest tag is a prerelease of a **different channel** (e.g. beta when asking for rc) → keep the base, restart at `.1` in the new channel: `vX.Y.Z-rc.1`
- if there is **no** prior tag → `v0.1.0` for `minor`, `v0.0.1` for `patch`, `v1.0.0` for `major`, `v0.0.1-rc.1` / `-beta.1` for prereleases.

**Files:**

- Create: `tests/scripts/test_next_version.py`
- Create: `scripts/release/next_version.py`

- [ ] **Step 1: Write the failing tests**

```python
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "release"))

from next_version import compute_next_version


@pytest.mark.parametrize(
    ("latest", "bump", "expected"),
    [
        ("v1.2.3", "patch", "v1.2.4"),
        ("v1.2.3", "minor", "v1.3.0"),
        ("v1.2.3", "major", "v2.0.0"),
        ("v1.2.3", "rc", "v1.2.4-rc.1"),
        ("v1.2.3", "beta", "v1.2.4-beta.1"),
        ("v1.2.4-rc.1", "rc", "v1.2.4-rc.2"),
        ("v1.2.4-beta.2", "beta", "v1.2.4-beta.3"),
        ("v1.2.4-beta.2", "rc", "v1.2.4-rc.1"),
        ("v1.2.4-rc.3", "patch", "v1.2.4"),
        ("v1.2.4-rc.3", "minor", "v1.3.0"),
        (None, "patch", "v0.0.1"),
        (None, "minor", "v0.1.0"),
        (None, "major", "v1.0.0"),
        (None, "rc", "v0.0.1-rc.1"),
    ],
)
def test_compute_next_version(latest, bump, expected):
    assert compute_next_version(latest, bump) == expected


def test_compute_next_version_rejects_unknown_bump():
    with pytest.raises(ValueError):
        compute_next_version("v1.2.3", "nonsense")


def test_compute_next_version_rejects_bad_tag():
    with pytest.raises(ValueError):
        compute_next_version("1.2.3", "patch")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/scripts/test_next_version.py -v --no-cov`
Expected: FAIL — `ModuleNotFoundError: No module named 'next_version'`.

- [ ] **Step 3: Implement `scripts/release/next_version.py`**

```python
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

BUMP_LEVELS = ("patch", "minor", "major", "rc", "beta")

_TAG_RE = re.compile(
    r"^v(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<channel>beta|rc)\.(?P<number>[1-9]\d*))?$"
)


@dataclass(frozen=True)
class _Parsed:
    major: int
    minor: int
    patch: int
    channel: str | None
    number: int | None


def _parse(tag: str) -> _Parsed:
    match = _TAG_RE.fullmatch(tag.strip())
    if match is None:
        raise ValueError(f"Cannot parse latest tag {tag!r}; expected vX.Y.Z[-(beta|rc).N]")
    return _Parsed(
        major=int(match.group("major")),
        minor=int(match.group("minor")),
        patch=int(match.group("patch")),
        channel=match.group("channel"),
        number=int(match.group("number")) if match.group("number") else None,
    )


def compute_next_version(latest: str | None, bump: str) -> str:
    if bump not in BUMP_LEVELS:
        raise ValueError(f"Unknown bump {bump!r}; expected one of {', '.join(BUMP_LEVELS)}")

    if latest is None:
        base = {"patch": (0, 0, 1), "minor": (0, 1, 0), "major": (1, 0, 0)}
        if bump in ("patch", "minor", "major"):
            major, minor, patch = base[bump]
            return f"v{major}.{minor}.{patch}"
        return f"v0.0.1-{bump}.1"

    parsed = _parse(latest)

    if bump in ("patch", "minor", "major"):
        # Finalizing an existing prerelease of X.Y.Z with "patch" yields X.Y.Z itself.
        if parsed.channel is not None and bump == "patch":
            return f"v{parsed.major}.{parsed.minor}.{parsed.patch}"
        if bump == "patch":
            return f"v{parsed.major}.{parsed.minor}.{parsed.patch + 1}"
        if bump == "minor":
            return f"v{parsed.major}.{parsed.minor + 1}.0"
        return f"v{parsed.major + 1}.0.0"

    # bump is "rc" or "beta"
    if parsed.channel == bump:
        return f"v{parsed.major}.{parsed.minor}.{parsed.patch}-{bump}.{(parsed.number or 0) + 1}"
    if parsed.channel is not None:
        # different prerelease channel on the same base: restart numbering
        return f"v{parsed.major}.{parsed.minor}.{parsed.patch}-{bump}.1"
    # latest is stable: prerelease of the next patch
    return f"v{parsed.major}.{parsed.minor}.{parsed.patch + 1}-{bump}.1"


def _latest_tag() -> str | None:
    try:
        out = subprocess.run(
            ["git", "tag", "--list", "v*", "--sort=-version:refname"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
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
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/scripts/test_next_version.py -v --no-cov`
Expected: all PASS.

- [ ] **Step 5: Lint**

Run: `uv run ruff check scripts/release/next_version.py tests/scripts/test_next_version.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add scripts/release/next_version.py tests/scripts/test_next_version.py
git commit -m "feat: add next-version computation for release prep"
```

---

## Task 5: Delete the duplicate workflow and dead scripts

**Files:**

- Delete: `.github/workflows/publish.yml`
- Delete: `scripts/release_automation.py`
- Delete: `tests/scripts/test_release_automation.py`
- Delete: `scripts/release/stub_build.py`

- [ ] **Step 1: Remove the files**

```bash
git rm -f .github/workflows/publish.yml
rm -f scripts/release_automation.py scripts/release/stub_build.py
rm -f tests/scripts/test_release_automation.py
```

(Only `publish.yml` is tracked, so `git rm` applies to it; the others are untracked and removed with `rm`.)

- [ ] **Step 2: Confirm nothing else references the deleted modules**

Run:

```bash
grep -rn "release_automation\|stub_build" --include="*.py" --include="*.yml" --include="*.yaml" --include="*.md" . | grep -v docs/superpowers
```

Expected: no output (the spec/plan under `docs/superpowers` may mention them — those are filtered out). If `release.yml` still references `stub_build.py`, that is fixed in Task 6; note it and continue.

- [ ] **Step 3: Verify the suite still passes**

Run: `uv run pytest tests/scripts/ -v --no-cov`
Expected: PASS, with no collection error for the deleted `test_release_automation.py`.

- [ ] **Step 4: Commit**

```bash
git add -A .github/workflows/publish.yml scripts/ tests/scripts/
git commit -m "chore: remove duplicate release workflow and stub scripts"
```

---

## Task 6: Rewrite `release.yml` for real build, test gate, and trusted publishing

**Files:**

- Modify: `.github/workflows/release.yml` (full replacement)

- [ ] **Step 1: Replace the entire file**

```yaml
name: Release

on:
  push:
    tags:
      - "v*.*.*"
  workflow_dispatch:
    inputs:
      release_tag:
        description: "Existing tag to release, for example v1.2.3-rc.1"
        required: true
        type: string

permissions:
  contents: read

concurrency:
  group: release-${{ github.event_name == 'workflow_dispatch' && inputs.release_tag || github.ref_name }}
  cancel-in-progress: false

jobs:
  prepare:
    name: Validate release
    runs-on: ubuntu-latest
    outputs:
      tag: ${{ steps.tag.outputs.tag }}
      version: ${{ steps.tag.outputs.version }}
      package_version: ${{ steps.tag.outputs.package_version }}
      channel: ${{ steps.tag.outputs.channel }}
      prerelease: ${{ steps.tag.outputs.prerelease }}
      publish_target: ${{ steps.tag.outputs.publish_target }}
      release_environment: ${{ steps.tag.outputs.release_environment }}
      title: ${{ steps.tag.outputs.title }}
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2

      - name: Resolve release tag
        id: resolve
        shell: bash
        env:
          EVENT_NAME: ${{ github.event_name }}
          INPUT_TAG: ${{ inputs.release_tag }}
          PUSH_TAG: ${{ github.ref_name }}
        run: |
          if [ "$EVENT_NAME" = "workflow_dispatch" ]; then
            tag="$INPUT_TAG"
          else
            tag="$PUSH_TAG"
          fi
          if [ -z "$tag" ]; then
            echo "::error::No release tag was provided."
            exit 1
          fi
          echo "tag=$tag" >> "$GITHUB_OUTPUT"

      - name: Parse release tag
        id: tag
        run: python scripts/release/parse_release_tag.py "${{ steps.resolve.outputs.tag }}"

      - name: Authorize release actor
        id: auth
        env:
          GITHUB_ACTOR: ${{ github.actor }}
          GITHUB_REPOSITORY_OWNER: ${{ github.repository_owner }}
          RELEASE_ACTORS: ${{ vars.RELEASE_ACTORS }}
        run: python scripts/release/check_release_actor.py

  test:
    name: Test gate
    needs: prepare
    runs-on: ubuntu-latest
    container: ghcr.io/astral-sh/uv:python3.13-bookworm
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
      - run: uv sync --group dev --group fast
      - run: uv run pytest

  build:
    name: Build artifacts
    needs: [prepare, test]
    runs-on: ubuntu-latest
    container: ghcr.io/astral-sh/uv:python3.13-bookworm
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
        with:
          fetch-depth: 0
          fetch-tags: true

      - name: Build package
        run: uv build

      - name: Verify built version matches the tag
        shell: bash
        env:
          PKG_VERSION: ${{ needs.prepare.outputs.package_version }}
        run: |
          set -euo pipefail
          if ! ls dist/generate_ledger-"$PKG_VERSION".tar.gz >/dev/null 2>&1; then
            echo "::error::Built artifacts do not match expected version $PKG_VERSION"
            ls -la dist
            exit 1
          fi
          ls -la dist

      - name: Upload dist
        uses: actions/upload-artifact@bbbca2ddaa5d8feaa63e36b76fdaad77386f024f # v7.0.0
        with:
          name: dist-${{ needs.prepare.outputs.tag }}
          path: dist/

  publish:
    name: Publish to ${{ needs.prepare.outputs.publish_target }}
    needs: [prepare, build]
    runs-on: ubuntu-latest
    environment:
      name: ${{ needs.prepare.outputs.release_environment }}
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2

      - uses: astral-sh/setup-uv@cec208311dfd045dd5311c1add060b2062131d57 # v8.0.0

      - name: Download dist
        uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1
        with:
          name: dist-${{ needs.prepare.outputs.tag }}
          path: dist/

      - name: Publish (trusted publishing)
        shell: bash
        env:
          TARGET: ${{ needs.prepare.outputs.publish_target }}
        run: |
          set -euo pipefail
          if [ "$TARGET" = "testpypi" ]; then
            uv publish --index testpypi --trusted-publishing always
          else
            uv publish --trusted-publishing always
          fi

  github-release:
    name: Create GitHub release
    needs: [prepare, build, publish]
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2

      - name: Download dist
        uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1
        with:
          name: dist-${{ needs.prepare.outputs.tag }}
          path: dist/

      - name: Write release notes
        shell: bash
        env:
          TITLE: ${{ needs.prepare.outputs.title }}
          TAG: ${{ needs.prepare.outputs.tag }}
          CHANNEL: ${{ needs.prepare.outputs.channel }}
          PACKAGE_VERSION: ${{ needs.prepare.outputs.package_version }}
          PUBLISH_TARGET: ${{ needs.prepare.outputs.publish_target }}
        run: |
          {
            echo "## $TITLE"
            echo ""
            echo "- Tag: \`$TAG\`"
            echo "- Channel: \`$CHANNEL\`"
            echo "- Package version: \`$PACKAGE_VERSION\`"
            echo "- Published to: \`$PUBLISH_TARGET\`"
            echo "- Commit: \`$GITHUB_SHA\`"
          } > release-notes.md
          cat release-notes.md >> "$GITHUB_STEP_SUMMARY"

      - name: Create or update release page
        shell: bash
        env:
          GH_TOKEN: ${{ github.token }}
          TAG: ${{ needs.prepare.outputs.tag }}
          TITLE: ${{ needs.prepare.outputs.title }}
          PRERELEASE: ${{ needs.prepare.outputs.prerelease }}
        run: |
          set -euo pipefail
          prerelease_args=()
          if [ "$PRERELEASE" = "true" ]; then
            prerelease_args+=(--prerelease)
          fi
          if gh release view "$TAG" >/dev/null 2>&1; then
            gh release upload "$TAG" dist/* --clobber
            gh release edit "$TAG" --title "$TITLE" --notes-file release-notes.md "${prerelease_args[@]}"
          else
            gh release create "$TAG" dist/* \
              --verify-tag \
              --target "$GITHUB_SHA" \
              --title "$TITLE" \
              --notes-file release-notes.md \
              "${prerelease_args[@]}"
          fi
```

- [ ] **Step 2: Lint the workflow with actionlint**

Run: `uvx --from actionlint-py actionlint .github/workflows/release.yml || docker run --rm -v "$(pwd)":/repo --workdir /repo rhysd/actionlint:latest -color .github/workflows/release.yml`
Expected: no errors. (If neither actionlint runner is available, validate YAML instead: `uv run python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/release.yml'))" && echo OK`.)

- [ ] **Step 3: Confirm no lingering stub references**

Run: `grep -n "stub" .github/workflows/release.yml`
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci: real build and trusted publishing in release workflow"
```

---

## Task 7: Add git-cliff configuration

**Files:**

- Create: `cliff.toml`

- [ ] **Step 1: Create `cliff.toml`**

```toml
# git-cliff configuration — generates changelog sections from conventional commits.
[changelog]
header = """
# Changelog

All notable changes to this project will be documented in this file.
"""
body = """
{% if version %}\
## {{ version | trim_start_matches(pat="v") }} - {{ timestamp | date(format="%Y-%m-%d") }}
{% else %}\
## [Unreleased]
{% endif %}\
{% for group, commits in commits | group_by(attribute="group") %}
### {{ group | upper_first }}
{% for commit in commits %}
- {{ commit.message | upper_first }}\
{% endfor %}
{% endfor %}\n
"""
trim = true

[git]
conventional_commits = true
filter_unconventional = true
split_commits = false
commit_parsers = [
  { message = "^feat", group = "Added" },
  { message = "^fix", group = "Fixed" },
  { message = "^perf", group = "Performance" },
  { message = "^refactor", group = "Changed" },
  { message = "^docs", group = "Documentation" },
  { message = "^test", group = "Tests" },
  { message = "^chore", skip = true },
  { message = "^ci", skip = true },
  { message = "^build", group = "Build" },
]
protect_breaking_commits = true
filter_commits = false
tag_pattern = "v[0-9]*"
sort_commits = "oldest"
```

- [ ] **Step 2: Verify git-cliff renders the unreleased section**

Run: `git-cliff --config cliff.toml --unreleased --strip all 2>&1 | head -30`
Expected: Markdown containing a `### Added` / `### Fixed` style section derived from recent commits (exact contents depend on history). No template errors.

- [ ] **Step 3: Commit**

```bash
git add cliff.toml
git commit -m "build: add git-cliff changelog configuration"
```

---

## Task 8: Create `release-prep.yml` (bump → changelog PR → tag-on-merge)

**Files:**

- Create: `.github/workflows/release-prep.yml`

- [ ] **Step 1: Create the workflow**

```yaml
name: Prepare release

on:
  workflow_dispatch:
    inputs:
      bump:
        description: "Version bump level"
        required: true
        type: choice
        options: [patch, minor, major, rc, beta]

permissions:
  contents: read

concurrency:
  group: release-prep
  cancel-in-progress: false

jobs:
  open-pr:
    name: Open changelog PR
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
        with:
          fetch-depth: 0
          fetch-tags: true

      - name: Compute next version
        id: next
        run: python scripts/release/next_version.py "${{ inputs.bump }}"

      - name: Generate changelog
        uses: orhun/git-cliff-action@4a4a951bc43fafe41cd2348d181853f52356bee7 # v4.4.2
        with:
          config: cliff.toml
          args: --unreleased --tag ${{ steps.next.outputs.tag }} --prepend CHANGELOG.md

      - name: Create pull request
        uses: peter-evans/create-pull-request@271a8d0340265f705b14b6d32b9829c1cb33d45e # v7.0.8
        with:
          branch: release/${{ steps.next.outputs.tag }}
          base: ${{ github.ref_name }}
          title: "release: ${{ steps.next.outputs.tag }}"
          body: |
            Automated release preparation for **${{ steps.next.outputs.tag }}** (bump: `${{ inputs.bump }}`).

            Merging this PR pushes the tag `${{ steps.next.outputs.tag }}`, which triggers the Release workflow
            (build → test → trusted publish → GitHub release).

            This PR changes only `CHANGELOG.md`. The package version is derived from the tag — nothing else to edit.
          labels: release
          add-paths: |
            CHANGELOG.md

  tag-on-merge:
    name: Tag merged release PR
    if: >-
      github.event_name == 'pull_request' &&
      github.event.pull_request.merged == true &&
      contains(github.event.pull_request.labels.*.name, 'release')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
        with:
          fetch-depth: 0
          token: ${{ secrets.RELEASE_PAT }}

      - name: Push release tag
        shell: bash
        env:
          HEAD_REF: ${{ github.event.pull_request.head.ref }}
        run: |
          set -euo pipefail
          tag="${HEAD_REF#release/}"
          echo "Tagging merge commit $GITHUB_SHA as $tag"
          git tag "$tag" "$GITHUB_SHA"
          git push origin "$tag"
```

- [ ] **Step 2: Add the `pull_request` trigger for the tag-on-merge job**

The `tag-on-merge` job needs a `pull_request` (closed) event. Update the top-level `on:` block to:

```yaml
on:
  workflow_dispatch:
    inputs:
      bump:
        description: "Version bump level"
        required: true
        type: choice
        options: [patch, minor, major, rc, beta]
  pull_request:
    types: [closed]
```

The `open-pr` job only runs on dispatch and `tag-on-merge` only on a merged PR, so add a guard to `open-pr` as well — set its `if:` to `github.event_name == 'workflow_dispatch'`. Final `open-pr` job header:

```yaml
open-pr:
  name: Open changelog PR
  if: github.event_name == 'workflow_dispatch'
  runs-on: ubuntu-latest
```

- [ ] **Step 3: Lint the workflow**

Run: `uvx --from actionlint-py actionlint .github/workflows/release-prep.yml || uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/release-prep.yml')); print('OK')"`
Expected: no errors / `OK`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/release-prep.yml
git commit -m "ci: add action-driven release prep workflow"
```

---

## Task 9: Documentation and housekeeping

**Files:**

- Modify: `CHANGELOG.md:1-6`
- Modify: `docs/release.md` (full replacement)
- Modify: `CLAUDE.md` (CI/architecture sections)

- [ ] **Step 1: Align `CHANGELOG.md` header with git-cliff**

Ensure the top of `CHANGELOG.md` matches what `cliff.toml` prepends, so prepends do not duplicate the header. Confirm lines 1-6 read:

```markdown
# Changelog

All notable changes to this project will be documented in this file.
```

Leave the existing `## [Unreleased]` and historical sections below intact. (If the existing "Keep a Changelog / SemVer" lines remain, that is fine — git-cliff `--prepend` inserts new version sections after the header block.)

- [ ] **Step 2: Replace `docs/release.md`**

```markdown
# Releasing

Releases are tag-driven. The git tag is the single source of truth for the version —
nothing is hardcoded in `pyproject.toml` (see `uv-dynamic-versioning`).

## Cutting a release

1. Go to **Actions → Prepare release → Run workflow** and pick a bump level
   (`patch`, `minor`, `major`, `rc`, `beta`).
2. Review the changelog PR it opens (titled `release: vX.Y.Z`). It changes only `CHANGELOG.md`.
3. Merge the PR. On merge, the tag `vX.Y.Z` is pushed automatically (using `RELEASE_PAT`),
   which triggers the **Release** workflow: test gate → `uv build` → `uv publish` (trusted) →
   GitHub Release.

`rc`/`beta` tags publish to **TestPyPI** (environment `prerelease`).
`stable`/`hotfix` tags publish to **PyPI** (environment `release`, gated by required reviewers).

## Tag formats

| Kind              | Tag example     | Index    | Environment  |
| ----------------- | --------------- | -------- | ------------ |
| Stable            | `v1.2.3`        | PyPI     | `release`    |
| Beta              | `v1.2.3-beta.1` | TestPyPI | `prerelease` |
| Release candidate | `v1.2.3-rc.1`   | TestPyPI | `prerelease` |
| Hotfix            | `v1.2.4.post1`  | PyPI     | `release`    |

## One-time setup (manual, in GitHub & PyPI settings)

1. Create GitHub Environments `release` and `prerelease`
   (**Settings → Environments**).
2. Add **required reviewers** to `release` (prod approval gate).
3. Register a **pending trusted publisher** on **PyPI** (project bound to this repo,
   workflow `release.yml`, environment `release`) and on **TestPyPI**
   (environment `prerelease`). See https://docs.pypi.org/trusted-publishers/.
4. Create a **fine-grained PAT** with `contents: write` (push tags) on this repo and
   store it as the repository secret **`RELEASE_PAT`**.
5. Set the **`RELEASE_ACTORS`** repository variable to a comma-separated list of
   GitHub usernames allowed to release.

## Rehearsal

Run **Release** via `workflow_dispatch` with an existing `rc`/`beta` tag to exercise the
full build/publish path against TestPyPI without touching PyPI.
```

- [ ] **Step 3: Update `CLAUDE.md` CI section**

Find the CI/workflow description (the project notes list `tests.yml` + `publish.yml`). Replace any mention of `publish.yml` and dual release workflows with:

```markdown
- `.github/workflows/release.yml` — single tag-driven Release workflow (validate → test gate → `uv build` → `uv publish` trusted publishing → GitHub Release). Versions are derived from git tags via `uv-dynamic-versioning`; no version is committed in `pyproject.toml`.
- `.github/workflows/release-prep.yml` — action-driven release prep: pick a bump level, it opens a changelog-only PR; merging the PR pushes the tag (via `RELEASE_PAT`) which triggers `release.yml`.
- Release helpers live in `scripts/release/` (`parse_release_tag.py`, `check_release_actor.py`, `next_version.py`), tested under `tests/scripts/`.
```

- [ ] **Step 4: Full verification**

Run:

```bash
uv run ruff check .
uv run pytest -q
```

Expected: ruff clean; tests pass with coverage ≥ 85%.

- [ ] **Step 5: Commit**

```bash
git add CHANGELOG.md docs/release.md CLAUDE.md
git commit -m "docs: document tag-driven release flow"
```

---

## Final verification (after all tasks)

- [ ] Run `uv run ruff check .` — clean.
- [ ] Run `uv run pytest` — passes, coverage ≥ 85%.
- [ ] Run `git tag v0.0.9-rc.1 && uv build && ls dist && git tag -d v0.0.9-rc.1 && rm -rf dist` — wheel/sdist named `...0.0.9rc1...`.
- [ ] Confirm only `tests.yml`, `release.yml`, `release-prep.yml` exist under `.github/workflows/`.
- [ ] Confirm `grep -rn "stub_build\|release_automation" --include=*.py --include=*.yml . | grep -v docs/superpowers` is empty.

## Notes on what is NOT automatable by this plan

The five **one-time setup** items in `docs/release.md` (environments, required reviewers, both trusted publishers, the `RELEASE_PAT` secret, the `RELEASE_ACTORS` variable) must be configured by a maintainer in GitHub/PyPI settings. Until the trusted publishers and `RELEASE_PAT` exist, `release.yml`'s `publish` job and `release-prep.yml`'s `tag-on-merge` job will fail at runtime — this is expected and is the handoff boundary.

```

```
