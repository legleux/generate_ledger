# Releasing

Releases are tag-driven. The git tag is the single source of truth for the version —
nothing is hardcoded in `pyproject.toml` (see `uv-dynamic-versioning`).

## Cutting a release

1. Go to **Actions → Prepare release → Run workflow** and pick a bump level
   (`patch`, `minor`, `major`, `rc`, `beta`, `hotfix`).
2. Review the changelog PR it opens (titled `release: vX.Y.Z`). It changes only `CHANGELOG.md`.
3. Merge the PR. On merge, the tag `vX.Y.Z` is pushed automatically (using `RELEASE_PAT`),
   which triggers the **Release** workflow: test gate → `uv build` → `uv publish` (trusted) →
   GitHub Release.

All releases — stable **and** pre-releases — publish to **PyPI** in the `release` environment.
Pre-releases (`rc`/`beta`) are PEP 440 pre-release versions (e.g. `1.2.3rc1`): `pip install`
skips them by default, and `pip install --pre generate-ledger` (or an explicit pin) opts in.
They are also marked as pre-releases on the GitHub Release page. (TestPyPI is a rehearsal
sandbox, not a release channel, so it is not part of this pipeline.)

## Tag formats

| Kind              | Tag example     | PyPI version  | GitHub pre-release |
| ----------------- | --------------- | ------------- | ------------------ |
| Stable            | `v1.2.3`        | `1.2.3`       | no                 |
| Beta              | `v1.2.3-beta.1` | `1.2.3b1`     | yes                |
| Release candidate | `v1.2.3-rc.1`   | `1.2.3rc1`    | yes                |
| Hotfix            | `v1.2.4.post1`  | `1.2.4.post1` | no                 |

## One-time setup (manual, in GitHub & PyPI settings)

1. Create the GitHub Environment `release` (**Settings → Environments**). GitHub also
   auto-creates it on first use.
2. _(Optional, recommended once there are multiple maintainers)_ Add **required
   reviewers** to `release` for a prod approval gate. For a solo maintainer this just
   means approving your own deploy, so it can be skipped.
3. Register a **pending trusted publisher** (no API token needed) on **PyPI**, using the
   values below. See <https://docs.pypi.org/trusted-publishers/> for the procedure
   (Account → Publishing → Add a pending publisher → GitHub). The environment must match the
   `release` environment that `release.yml` publishes from:

   | Field        | Value             |
   | ------------ | ----------------- |
   | Project name | `generate-ledger` |
   | Owner        | `legleux`         |
   | Repository   | `generate_ledger` |
   | Workflow     | `release.yml`     |
   | Environment  | `release`         |

4. Create a **fine-grained PAT** with `contents: write` (push tags) on this repo and
   store it as the repository secret **`RELEASE_PAT`** (used to push the release tag so it
   triggers `release.yml` — a `GITHUB_TOKEN`-pushed tag would not).
5. _(Optional)_ Set the **`RELEASE_ACTORS`** repository variable to a comma-separated list
   of GitHub usernames allowed to release. If unset, `check_release_actor.py` falls back to
   the repository owner, so a solo maintainer can skip this.

## Verifying a build

To check that the package builds and the version resolves correctly before tagging:

```bash
uv build && ls dist/
```

The artifact filename is the published version (e.g. `generate_ledger-1.2.3rc1-...`). Inspect
metadata with `uv run python -m twine check dist/*` if desired.
