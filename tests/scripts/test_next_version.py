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
        ("v1.2.3", "hotfix", "v1.2.3.post1"),
        ("v1.2.4-rc.1", "rc", "v1.2.4-rc.2"),
        ("v1.2.4-beta.2", "beta", "v1.2.4-beta.3"),
        ("v1.2.4-beta.2", "rc", "v1.2.4-rc.1"),
        ("v1.2.4-rc.3", "patch", "v1.2.4"),
        ("v1.2.4-rc.3", "minor", "v1.3.0"),
        ("v1.2.3.post1", "hotfix", "v1.2.3.post2"),
        ("v1.2.3.post1", "patch", "v1.2.4"),
        ("v1.2.3.post1", "rc", "v1.2.4-rc.1"),
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


@pytest.mark.parametrize(("latest", "bump"), [(None, "hotfix"), ("v1.2.4-rc.1", "hotfix")])
def test_compute_next_version_rejects_bad_hotfix_source(latest, bump):
    with pytest.raises(ValueError):
        compute_next_version(latest, bump)


@pytest.mark.parametrize("latest", ["v0.0.4a4", "v1.2.3b1", "v1.2.3rc1"])
def test_compute_next_version_rejects_unsupported_latest_tags(latest):
    with pytest.raises(ValueError):
        compute_next_version(latest, "patch")
