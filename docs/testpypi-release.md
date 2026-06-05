# TestPyPI Release Rehearsal

This is a no-prod rehearsal for the tag-driven release pipeline. The current
`release.yml` publishes to real PyPI, so do not push a throwaway tag until the
temporary TestPyPI publish target below is in place.

Git tags are `v`-prefixed, but PyPI/TestPyPI package versions are not. For
example, tag `v0.0.1-rc.1` publishes package version `0.0.1rc1`.

## Supported Throwaway Tags

Use a version that has never been uploaded to TestPyPI. Published filenames are
effectively burned, so use a new tag number if you rerun the rehearsal.

| Kind              | Tag             | Package version |
| ----------------- | --------------- | --------------- |
| Beta              | `v0.0.1-beta.1` | `0.0.1b1`       |
| Release candidate | `v0.0.1-rc.1`   | `0.0.1rc1`      |
| Stable smoke      | `v0.0.1`        | `0.0.1`         |

Prefer `rc` or `beta` for rehearsals so the GitHub Release is marked as a
pre-release.

## CI Rehearsal With Trusted Publishing

This path tests the real GitHub Actions build and trusted publishing flow.

1. In TestPyPI, create a pending trusted publisher:

   | Field        | Value             |
   | ------------ | ----------------- |
   | Project name | `generate-ledger` |
   | Owner        | `legleux`         |
   | Repository   | `generate_ledger` |
   | Workflow     | `release.yml`     |
   | Environment  | `testpypi`        |

2. In GitHub, create the environment `testpypi`.

   Do not add required reviewers for the rehearsal unless you want the publish
   job to pause. Keep the real `release` environment for production PyPI.

3. On a temporary rehearsal branch, change only the `publish` job in
   `.github/workflows/release.yml`:

   ```yaml
   publish:
     name: Publish to TestPyPI
     needs: [prepare, build]
     runs-on: ubuntu-latest
     environment:
       name: testpypi
     permissions:
       contents: read
       id-token: write
     steps:
       - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2

       - uses: astral-sh/setup-uv@cec208311dfd045dd5311c1add060b2062131d57 # v8.0.0

       - name: Download dist
         uses: actions/download-artifact@37930b1c2abaa49bbe596cd826c3c89aef350131 # v7.0.0
         with:
           name: dist-${{ needs.prepare.outputs.tag }}
           path: dist/

       - name: Publish to TestPyPI (trusted publishing)
         run: >
           uv publish --trusted-publishing always
           --publish-url https://test.pypi.org/legacy/
           --check-url https://test.pypi.org/simple/
   ```

4. Commit and push the temporary branch.

   ```bash
   git switch -c testpypi-release-rehearsal
   git add .github/workflows/release.yml
   git commit -m "ci: rehearse release against testpypi"
   git push origin testpypi-release-rehearsal
   ```

5. Push a throwaway tag that points at the temporary branch commit.

   ```bash
   git tag v0.0.1-rc.1
   git push origin v0.0.1-rc.1
   ```

6. Watch the `Release` workflow.

   Expected path:
   - `prepare` parses `v0.0.1-rc.1` as package version `0.0.1rc1`.
   - `test` runs the normal pytest gate.
   - `build` creates real sdist and wheel artifacts.
   - `publish` uploads to TestPyPI using OIDC trusted publishing.
   - `github-release` creates or updates a pre-release page for the tag.

7. Verify TestPyPI install.

   TestPyPI does not mirror all dependencies, so install dependencies from PyPI
   with `--extra-index-url`.

   ```bash
   python -m venv /tmp/generate-ledger-testpypi
   /tmp/generate-ledger-testpypi/bin/python -m pip install --upgrade pip
   /tmp/generate-ledger-testpypi/bin/python -m pip install \
     --index-url https://test.pypi.org/simple/ \
     --extra-index-url https://pypi.org/simple/ \
     --pre \
     generate-ledger==0.0.1rc1
   /tmp/generate-ledger-testpypi/bin/gen --help
   ```

8. Clean up GitHub release/tag and the temporary branch.

   ```bash
   gh release delete v0.0.1-rc.1 --yes
   git push origin :refs/tags/v0.0.1-rc.1
   git tag -d v0.0.1-rc.1
   git push origin --delete testpypi-release-rehearsal
   ```

   If TestPyPI keeps the uploaded files, leave them there and use a new version
   for the next rehearsal.

## Local Token Smoke Test

This path proves the built package can upload to TestPyPI, but it does not test
GitHub trusted publishing.

1. Create a TestPyPI API token and export it locally.

   ```bash
   export UV_PUBLISH_TOKEN="pypi-..."
   ```

2. Build from a throwaway tag.

   ```bash
   git tag v0.0.1-rc.1
   uv build
   ```

3. Publish to TestPyPI.

   ```bash
   uv publish \
     --publish-url https://test.pypi.org/legacy/ \
     --check-url https://test.pypi.org/simple/
   ```

4. Delete the local tag after the build.

   ```bash
   git tag -d v0.0.1-rc.1
   ```

## Sources

- PyPI trusted publishing: <https://docs.pypi.org/trusted-publishers/>
- PyPI publishing with trusted publishers: <https://docs.pypi.org/trusted-publishers/using-a-publisher/>
- uv package publishing guide: <https://docs.astral.sh/uv/guides/package/>
- uv publish/check URL settings: <https://docs.astral.sh/uv/reference/settings/>
