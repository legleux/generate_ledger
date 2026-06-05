# Release pipeline consolidation + tag-driven dynamic versioning

|                     |                                                                                         |
| ------------------- | --------------------------------------------------------------------------------------- |
| **Date:**           | 2026-06-04                                                                              |
| **Branch context:** | `features-amm-test-n-publish` (the "publish" half — AMM/MPT smoke tests already landed) |
| **Status:**         | Approved design, ready for implementation planning                                      |

## Problem

The repository currently has **two competing GitHub Actions workflows both named `Release`**, both triggering on a version-tag push:

- `.github/workflows/publish.yml` — older draft, helper `scripts/release_automation.py`, stubbed build/publish.
- `.github/workflows/release.yml` — newer, better-factored rewrite (modular `scripts/release/*.py`, per-channel `environment`, separate publish + github-release jobs), still stubbed build/publish.

Pushing a tag like `v1.2.3` fires **both**, racing to create the same GitHub Release page. On top of that, **every helper script both workflows depend on is untracked in git**, so a clean-checkout CI run would fail. Build and publish are placeholders (`stub_build.py`, "would publish") — there is no real package publishing. `pyproject.toml` pins a static `version = "0.0.8"` while the tag parser derives a `package_version` from the tag, so a real upload would risk a tag/metadata mismatch.

## Goals

1. **One** release workflow; the duplicate and its dead scripts removed and the survivors committed.
2. **Real publishing** to PyPI / TestPyPI via uv, using **trusted publishing (OIDC)** — no stored index credentials.
3. **No version committed anywhere in the tree**; the git tag is the single source of truth (dynamic versioning).
4. **Action-driven, PR-reviewed releases** — a maintainer never types a version by hand. Trigger an Action, review a changelog PR, merge, and it ships.
5. GitHub **Environments** doing real work: scoping the trusted publisher and gating prod publishes behind a manual approval.

## Non-goals

- Renaming the package to `ledgen` (tracked separately).
- Changing what `tests.yml` covers, beyond reusing the suite as a release gate.
- Multi-registry publishing beyond PyPI + TestPyPI.

## Key decisions

| #       | Decision                     | Choice                                                                                              |
| ------- | ---------------------------- | --------------------------------------------------------------------------------------------------- |
| Auth    | Index authentication         | **Trusted publishing (OIDC)** via `uv publish` — no secrets                                         |
| Backend | Build backend                | **`hatchling`** (uv's native `uv_build` cannot do VCS versioning as of uv #14946)                   |
| Version | Version source               | **Dynamic from git tags** via the `uv-dynamic-versioning` hatchling plugin; nothing committed       |
| Tooling | Build/publish commands       | **`uv build`** + **`uv publish --trusted-publishing automatic`**                                    |
| Flow    | Release model                | **Approach A** — tag is truth; the bump is computed in an Action; the PR carries only the changelog |
| 3a      | Test gate before publish     | **Yes** — run `pytest` in the release pipeline before publishing                                    |
| 4a      | merge → tag → release bridge | **Fine-grained PAT** (a `GITHUB_TOKEN`-pushed tag will not trigger another workflow)                |
| 4b      | Changelog generation         | **git-cliff** (conventional commits are already enforced)                                           |
| Env     | Prod approval gate           | **Required reviewers on `release` only**; `prerelease` flows straight through                       |
| Env     | PAT storage                  | **Plain repository secret**                                                                         |

### Why not uv's native backend

`uv build` is a build _frontend_; it always drives a PEP 517 _backend_ declared in `[build-system]`. uv's own backend (`uv_build`) does not support deriving the version from git tags (open request: astral-sh/uv#14946). Tag-based versioning therefore requires a backend with a VCS version plugin — `hatchling` + `uv-dynamic-versioning` (a uv-tuned hatchling plugin). The commands run everywhere remain `uv build` / `uv publish`; hatchling is invisible plumbing.

### Why Approach A over alternatives

`uv version --bump` edits the committed `version` field in `pyproject.toml` — fundamentally incompatible with goal #3 ("no version committed"). Approach A reproduces the _experience_ of a one-click bump (an Action with a `patch`/`minor`/`major`/`rc`/`beta` choice) without a committed version to edit: it computes the next version from the latest tag and surfaces it in a changelog PR. The tag, created on merge, is the only artifact that records the version.

## Architecture

### Component 1 — Packaging (`pyproject.toml`)

- Keep `build-backend = "hatchling.build"`.
- Add `uv-dynamic-versioning` to `[build-system].requires` and register it as the hatch version source.
- `[project]`: remove `version = "0.0.8"`; add `dynamic = ["version"]`.
- Add `[tool.uv-dynamic-versioning]` (git VCS, PEP 440 style) including a **`fallback-version`** so Dependabot and sandboxed/no-git builds do not fail (per the plugin's tips doc).
- Result: the package version is computed from `git describe` / the current tag at build time. The PEP 440 output (e.g. `0.0.8rc1`) matches what `parse_release_tag.py` already computes as `package_version`, so they line up.

### Component 2 — Workflow consolidation

Delete:

- `.github/workflows/publish.yml`
- `scripts/release_automation.py`
- `tests/scripts/test_release_automation.py` (imports the deleted module)
- `scripts/release/stub_build.py` (replaced by real `uv build`)

Keep and commit (currently untracked):

- `.github/workflows/release.yml` — the single Release workflow.
- `scripts/release/parse_release_tag.py`
- `scripts/release/check_release_actor.py`

### Component 3 — `release.yml` (real publishing)

Trigger: `push` on tags `v*.*.*`, plus `workflow_dispatch` for rehearsal. Jobs:

1. **prepare** — `parse_release_tag.py` (channel / prerelease / title / `release_environment`) + `check_release_actor.py` (authorize actor against `RELEASE_ACTORS`). Kept essentially as-is.
2. **test (gate)** — run `uv run pytest` on the tagged commit. Tag pushes do not trigger `tests.yml`, and a published PyPI version is irreversible, so the suite runs here before anything is published. (May be a dedicated job that `build`/`publish` depend on, or a step in `build`.)
3. **build** — checkout with `fetch-depth: 0` and tags fetched so `uv-dynamic-versioning` sees the tag; `uv build` → real sdist + wheel whose version equals the tag → upload `dist/` artifact.
4. **publish** — `uv publish --trusted-publishing automatic`; `permissions: id-token: write`; `environment: name: <release_environment>`. **Channel → index:** `beta`/`rc` → **TestPyPI**, `stable`/`hotfix` → **PyPI** (TestPyPI selected via the appropriate `--index` / publish URL). No stored index credentials.
5. **github-release** — create or update the GitHub Release with the real artifacts and notes. Mostly kept; already idempotent (existing-release check + `--clobber`).

### Component 4 — `release-prep.yml` (the action-driven bump)

Trigger: `workflow_dispatch` with input `bump` ∈ {`patch`, `minor`, `major`, `rc`, `beta`}.

Steps:

1. Checkout with tags.
2. `scripts/release/next_version.py` computes the next version from the latest matching tag, reusing `parse_release_tag.py` semantics. This replaces `uv version --bump` (which cannot operate without a committed version).
3. Generate the changelog section with **git-cliff** from conventional commits since the last tag; write/prepend `CHANGELOG.md`.
4. Open a PR from branch `release/vX.Y.Z` whose diff is **only `CHANGELOG.md`**, with the target version in the PR title/body and a `release` label. (Uses `peter-evans/create-pull-request` or `gh`.)

Merge → tag bridge:

- On merge of the release PR, a `tag-on-merge` job (in `release-prep.yml` or a small dedicated workflow) reads the version from the merged PR (title/label) and pushes tag `vX.Y.Z` **using the fine-grained PAT** (repo secret). A `GITHUB_TOKEN`-pushed tag would not trigger `release.yml`; the PAT push does.
- The pushed tag triggers `release.yml` (Component 3).

### Component 5 — GitHub Environments

Two environments, derived from channel via `parse_release_tag.py`'s `release_environment` output:

| Channel            | Environment  | Index    |
| ------------------ | ------------ | -------- |
| `beta`, `rc`       | `prerelease` | TestPyPI |
| `stable`, `hotfix` | `release`    | PyPI     |

Roles:

1. **Trusted-publisher scoping** — each pending publisher on PyPI/TestPyPI is bound to `repo + release.yml + environment name`, so a build outside the named environment cannot mint a publish token.
2. **Manual approval gate** — **required reviewers on `release` only**; `prerelease`/TestPyPI flows straight through. Flow: merge changelog PR → tag → build → `release` env pauses for approval → publish to PyPI.
3. **Secret scoping** — `RELEASE_ACTORS` variable; the PAT is a plain repository secret (the `tag-on-merge` job has no environment).

Environment protection rules (required reviewers) are configured in **repo settings / API, not YAML** — the workflow only names the environment. Setup is therefore a documented manual checklist (below), not code.

## Data flow

```
maintainer: Actions -> "Prepare release" -> pick bump (patch/minor/major/rc/beta)
  -> release-prep.yml: next_version.py computes vX.Y.Z; git-cliff writes CHANGELOG
  -> opens PR (release/vX.Y.Z, diff = CHANGELOG only)
maintainer: reviews + merges PR
  -> tag-on-merge: push tag vX.Y.Z using PAT  (PAT push so the next workflow fires)
  -> release.yml on tag push:
       prepare (parse + authorize)
       -> test gate (pytest)
       -> build (uv build; version = tag via uv-dynamic-versioning)
       -> publish (uv publish --trusted-publishing; env=release|prerelease; PyPI|TestPyPI)
            [release env: pauses for required-reviewer approval]
       -> github-release (real artifacts + notes)
```

## Error handling & edge cases

- **Invalid tag / unauthorized actor** → `prepare` fails fast (existing scripts already exit non-zero with `::error::`).
- **Version/metadata mismatch** → structurally impossible; the tag is the single source.
- **No git history (Dependabot, sandbox)** → `fallback-version` in `[tool.uv-dynamic-versioning]`.
- **Tag not triggering release** → resolved by pushing the tag with the PAT rather than `GITHUB_TOKEN`.
- **Trusted publishing prerequisite** → a one-time "pending publisher" registration on **both** PyPI and TestPyPI, bound to the environment names. Manual, documented, not automatable.
- **Re-runs / pre-existing release** → `release.yml` is idempotent (existing-release check + `--clobber`); the `concurrency` group prevents races.
- **Failed publish after a tag exists** → the tag remains; re-running `release.yml` (or the `workflow_dispatch` path) republishes idempotently.

## Testing

- **Add** unit tests for `scripts/release/parse_release_tag.py`, `check_release_actor.py`, and the new `next_version.py`. The kept scripts currently have **no** tests — the only release test (`test_release_automation.py`) covers the module being deleted.
- Keep coverage ≥ 85% (`scripts/**` is already in ruff per-file-ignores).
- Rehearsal path: `release.yml`'s `workflow_dispatch` + the TestPyPI/`prerelease` channel act as a no-prod dry run.

## Docs & housekeeping

- Flesh out the (currently untracked) `docs/release.md`:
  - How to cut a release (dispatch "Prepare release" → review PR → merge).
  - **Manual setup checklist:** create `release` and `prerelease` environments; set required reviewers on `release`; register pending trusted publishers on PyPI and TestPyPI bound to the environment names; add the fine-grained PAT as a repo secret; set the `RELEASE_ACTORS` variable.
  - Channel → environment → index mapping.
- Update `CLAUDE.md`'s CI section (it lists `tests.yml` + `publish.yml`) to describe the single `release.yml` + `release-prep.yml` and dynamic versioning.

## Manual prerequisites (one-time, outside this change)

1. Create GitHub Environments `release` and `prerelease`.
2. Add required reviewers to `release`.
3. Register a pending trusted publisher on **PyPI** (env `release`) and on **TestPyPI** (env `prerelease`), each bound to this repo + `release.yml`.
4. Create a fine-grained PAT with permission to push tags; store it as a repository secret for `release-prep.yml`'s tag-on-merge step.
5. Set the `RELEASE_ACTORS` repository variable.

## Affected files

| Action      | Path                                                                             |
| ----------- | -------------------------------------------------------------------------------- |
| Edit        | `pyproject.toml` (dynamic version, plugin, fallback)                             |
| Delete      | `.github/workflows/publish.yml`                                                  |
| Delete      | `scripts/release_automation.py`                                                  |
| Delete      | `tests/scripts/test_release_automation.py`                                       |
| Delete      | `scripts/release/stub_build.py`                                                  |
| Edit        | `.github/workflows/release.yml` (real build/publish, test gate)                  |
| Add         | `.github/workflows/release-prep.yml`                                             |
| Add         | `scripts/release/next_version.py`                                                |
| Keep/commit | `scripts/release/parse_release_tag.py`, `scripts/release/check_release_actor.py` |
| Add         | `tests/scripts/` tests for the kept + new release scripts                        |
| Edit/commit | `docs/release.md`                                                                |
| Edit        | `CLAUDE.md` (CI section)                                                         |
| Config      | `cliff.toml` (git-cliff)                                                         |
