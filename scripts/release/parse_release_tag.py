"""Parse and classify release tags for the GitHub release workflow."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass

SUPPORTED_TAGS = (
    "v1.2.3",
    "v1.2.3-beta.1",
    "v1.2.3-rc.1",
    "v1.2.4.post1",
)

TAG_RE = re.compile(
    r"""
    ^v
    (?P<major>0|[1-9]\d*)\.
    (?P<minor>0|[1-9]\d*)\.
    (?P<patch>0|[1-9]\d*)
    (?:
        -
        (?P<prerelease_channel>beta|rc)\.
        (?P<prerelease_number>[1-9]\d*)
      |
        \.post
        (?P<post_number>[1-9]\d*)
    )?
    $
    """,
    re.VERBOSE,
)


class InvalidReleaseTag(ValueError):
    """Raised when a tag does not match the supported release syntax."""


@dataclass(frozen=True)
class ReleaseTag:
    tag: str
    version: str
    package_version: str
    major: int
    minor: int
    patch: int
    channel: str
    qualifier_number: int | None
    prerelease: bool
    title: str

    def as_github_outputs(self) -> dict[str, str]:
        outputs = asdict(self)
        return {key: _github_output_value(value) for key, value in outputs.items()}


def parse_release_tag(tag: str) -> ReleaseTag:
    clean_tag = _clean_tag(tag)
    match = TAG_RE.fullmatch(clean_tag)
    if match is None:
        examples = ", ".join(SUPPORTED_TAGS)
        raise InvalidReleaseTag(f"Unsupported release tag {tag!r}. Expected one of: {examples}")

    major = int(match.group("major"))
    minor = int(match.group("minor"))
    patch = int(match.group("patch"))
    base_version = f"{major}.{minor}.{patch}"
    channel = "stable"
    qualifier_number: int | None = None
    package_version = base_version

    prerelease_channel = match.group("prerelease_channel")
    post_number = match.group("post_number")

    if prerelease_channel is not None:
        channel = prerelease_channel
        qualifier_number = int(match.group("prerelease_number"))
        package_version = _package_version(base_version, channel, qualifier_number)
    elif post_number is not None:
        channel = "hotfix"
        qualifier_number = int(post_number)
        package_version = f"{base_version}.post{qualifier_number}"

    # Pre-releases (rc/beta) are first-class PEP 440 versions published to PyPI just like
    # stable releases; `prerelease` only marks the GitHub Release and the version qualifier.
    # (TestPyPI is a rehearsal sandbox, not a release channel, so it plays no part here.)
    prerelease = channel in {"beta", "rc"}

    return ReleaseTag(
        tag=clean_tag,
        version=clean_tag.removeprefix("v"),
        package_version=package_version,
        major=major,
        minor=minor,
        patch=patch,
        channel=channel,
        qualifier_number=qualifier_number,
        prerelease=prerelease,
        title=_release_title(clean_tag, channel, qualifier_number),
    )


def _clean_tag(tag: str) -> str:
    clean_tag = tag.strip()
    if clean_tag.startswith("refs/tags/"):
        clean_tag = clean_tag.removeprefix("refs/tags/")
    return clean_tag


def _package_version(base_version: str, channel: str, qualifier_number: int) -> str:
    if channel == "beta":
        return f"{base_version}b{qualifier_number}"
    if channel == "rc":
        return f"{base_version}rc{qualifier_number}"
    if channel == "hotfix":
        return f"{base_version}.post{qualifier_number}"
    return base_version


def _release_title(tag: str, channel: str, qualifier_number: int | None) -> str:
    if channel == "stable":
        return f"generate-ledger {tag}"
    if qualifier_number is None:
        return f"generate-ledger {tag}"
    label = "beta" if channel == "beta" else channel
    return f"generate-ledger {tag} ({label} {qualifier_number})"


def _github_output_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def _write_github_outputs(outputs: dict[str, str]) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        for key, value in outputs.items():
            handle.write(f"{key}={value}\n")


def _write_step_summary(release_tag: ReleaseTag) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write("## Release tag\n\n")
        handle.write(f"- Tag: `{release_tag.tag}`\n")
        handle.write(f"- Channel: `{release_tag.channel}`\n")
        handle.write(f"- Package version: `{release_tag.package_version}`\n")
        handle.write(f"- GitHub prerelease: `{_github_output_value(release_tag.prerelease)}`\n\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag", help="Release tag or refs/tags/<tag> ref to parse")
    args = parser.parse_args(argv)

    try:
        release_tag = parse_release_tag(args.tag)
    except InvalidReleaseTag as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 2

    outputs = release_tag.as_github_outputs()
    _write_github_outputs(outputs)
    _write_step_summary(release_tag)
    print(json.dumps(outputs, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
