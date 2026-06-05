import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "release"))

from parse_release_tag import InvalidReleaseTag, parse_release_tag


@pytest.mark.parametrize(
    ("tag", "channel", "package_version", "prerelease"),
    [
        ("v1.2.3", "stable", "1.2.3", False),
        ("v1.2.3-beta.1", "beta", "1.2.3b1", True),
        ("v1.2.3-rc.2", "rc", "1.2.3rc2", True),
        ("v1.2.4.post1", "hotfix", "1.2.4.post1", False),
    ],
)
def test_parse_release_tag_classifies(tag, channel, package_version, prerelease):
    result = parse_release_tag(tag)
    assert result.tag == tag
    assert result.channel == channel
    assert result.package_version == package_version
    assert result.prerelease is prerelease


def test_parse_release_tag_strips_refs_prefix():
    result = parse_release_tag("refs/tags/v1.2.3")
    assert result.tag == "v1.2.3"
    assert result.version == "1.2.3"


@pytest.mark.parametrize(
    "tag",
    ["1.2.3", "v1.2", "v1.2.3-alpha.1", "v01.2.3", "v1.2.3-rc", "v1.2.3b1", "v1.2.3rc1"],
)
def test_parse_release_tag_rejects_unsupported(tag):
    with pytest.raises(InvalidReleaseTag):
        parse_release_tag(tag)


def test_as_github_outputs_stringifies_bools():
    outputs = parse_release_tag("v1.2.3-rc.1").as_github_outputs()
    assert outputs["prerelease"] == "true"
    assert outputs["channel"] == "rc"
    assert outputs["qualifier_number"] == "1"
