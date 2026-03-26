"""Amendment loading, hashing, features.macro parsing, and profile-based selection."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from urllib.parse import urlparse

from generate_ledger import data_dir
from generate_ledger.crypto import sha512_half

network_endpoint = {
    "devnet": "https://s.devnet.rippletest.net:51234",
    "testnet": "https://s.altnet.rippletest.net:51234",
    "mainnet": "https://s1.ripple.com:51234",
}

DEFAULT_NETWORK = "devnet"

# Amendment data file names
MAINNET_AMENDMENTS_FILE = "amendments_mainnet.json"

# Resolved paths
DEFAULT_MAINNET_LIST = data_dir / MAINNET_AMENDMENTS_FILE

# GitHub raw URL for the develop branch features.macro
FEATURES_MACRO_URL = (
    "https://raw.githubusercontent.com/XRPLF/rippled/develop/include/xrpl/protocol/detail/features.macro"
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Amendment:
    name: str
    index: str  # SHA512Half hex (uppercase)
    enabled: bool
    obsolete: bool = False
    supported: bool = True
    vote_behavior: str = "DefaultNo"  # "DefaultYes" or "DefaultNo"
    retired: bool = False


class AmendmentProfile(StrEnum):
    RELEASE = "release"  # Curated JSON for latest official xrpld release
    DEVELOP = "develop"  # Parse from features.macro, enable DefaultYes + Supported::yes
    CUSTOM = "custom"  # User-provided JSON file


# ---------------------------------------------------------------------------
# Hash computation
# ---------------------------------------------------------------------------


def amendment_hash(name: str) -> str:
    """SHA512Half(name) as uppercase hex — matches xrpld's Feature.cpp."""
    return sha512_half(name.encode("ascii")).hex().upper()


# ---------------------------------------------------------------------------
# features.macro parser
# ---------------------------------------------------------------------------

# Active: XRPL_FEATURE(Name, Supported::yes, VoteBehavior::DefaultYes)
#         XRPL_FIX(Name, Supported::yes, VoteBehavior::DefaultNo)
#         Also handles VoteBehavior::Obsolete (supported but never activated)
_RE_ACTIVE = re.compile(
    r"XRPL_(FEATURE|FIX)\s*\(\s*(\w+)\s*,"
    r"\s*Supported::(yes|no)\s*,"
    r"\s*VoteBehavior::(DefaultYes|DefaultNo|Obsolete)\s*\)"
)

# Retired (modern): XRPL_RETIRE(Name) — name used as-is (includes any "fix" prefix)
_RE_RETIRED = re.compile(r"XRPL_RETIRE\s*\(\s*(\w+)\s*\)")

# Retired (legacy): XRPL_RETIRE_FEATURE(Name) / XRPL_RETIRE_FIX(Name)
_RE_RETIRED_LEGACY = re.compile(r"XRPL_RETIRE_(FEATURE|FIX)\s*\(\s*(\w+)\s*\)")


def _derive_name(kind: str, raw_name: str) -> str:
    """XRPL_FIX(Foo) -> 'fixFoo', XRPL_FEATURE(Foo) -> 'Foo'."""
    if kind == "FIX":
        return f"fix{raw_name}"
    return raw_name


def parse_features_macro_text(text: str) -> list[Amendment]:
    """Parse features.macro content into a list of Amendments.

    All amendments are returned with ``enabled=False``; use
    ``apply_develop_profile()`` or ``get_amendments_for_profile()``
    to decide which to enable.
    """
    amendments: list[Amendment] = []

    # Active amendments
    for m in _RE_ACTIVE.finditer(text):
        kind, raw_name, supported, vote = m.groups()
        name = _derive_name(kind, raw_name)
        amendments.append(
            Amendment(
                name=name,
                index=amendment_hash(name),
                enabled=False,
                supported=(supported == "yes"),
                vote_behavior=vote,
                retired=False,
            )
        )

    # Retired amendments (modern format: XRPL_RETIRE(Name))
    for m in _RE_RETIRED.finditer(text):
        name = m.group(1)
        amendments.append(
            Amendment(
                name=name,
                index=amendment_hash(name),
                enabled=False,
                supported=True,
                vote_behavior="DefaultYes",
                retired=True,
            )
        )

    # Retired amendments (legacy format: XRPL_RETIRE_FEATURE/FIX(Name))
    for m in _RE_RETIRED_LEGACY.finditer(text):
        kind, raw_name = m.groups()
        name = _derive_name(kind, raw_name)
        # Skip if already captured by the modern regex
        if not any(a.name == name for a in amendments):
            amendments.append(
                Amendment(
                    name=name,
                    index=amendment_hash(name),
                    enabled=False,
                    supported=True,
                    vote_behavior="DefaultYes",
                    retired=True,
                )
            )

    return amendments


def parse_features_macro(path: str | Path) -> list[Amendment]:
    """Parse xrpld's features.macro file into a list of Amendments."""
    return parse_features_macro_text(Path(path).read_text())


def fetch_features_macro(url: str = FEATURES_MACRO_URL, *, timeout: int = 10) -> str:
    """Fetch features.macro content from a URL. Returns the raw text."""
    req = urllib.request.Request(url)
    response = urllib.request.urlopen(req, timeout=timeout)
    return response.read().decode("utf-8")


def resolve_develop_source(explicit_source: str | Path | None = None) -> list[Amendment]:
    """Resolve develop amendments via: explicit path → GitHub fetch → GL_FEATURES_MACRO env var.

    Returns parsed (but not yet profile-applied) amendments.
    Raises RuntimeError if all sources fail.
    """
    # 1. Explicit --amendment-source takes priority
    if explicit_source is not None:
        return parse_features_macro(explicit_source)

    # 2. Try GitHub fetch
    try:
        text = fetch_features_macro()
        return parse_features_macro_text(text)
    except (urllib.error.URLError, OSError, TimeoutError):
        pass

    # 3. Try GL_FEATURES_MACRO env var
    env_path = os.environ.get("GL_FEATURES_MACRO")
    if env_path:
        p = Path(env_path)
        if p.is_file():
            return parse_features_macro(p)

    # 4. All failed
    raise RuntimeError(
        "Could not load develop amendments. GitHub fetch failed and "
        "GL_FEATURES_MACRO is not set.\n"
        "Options:\n"
        "  1. Set GL_FEATURES_MACRO=/path/to/xrpld/.../features.macro\n"
        "  2. Use --amendment-source /path/to/features.macro\n"
        "  3. Use --amendment-profile release (curated mainnet amendments)"
    )


def apply_develop_profile(amendments: list[Amendment]) -> list[Amendment]:
    """Enable amendments appropriate for a develop build.

    Enables: all Supported::yes non-obsolete amendments, plus all retired.
    Obsolete amendments (supported but never activated) are left disabled.
    """
    result = []
    for a in amendments:
        should_enable = a.retired or (a.supported and a.vote_behavior != "Obsolete")
        result.append(
            Amendment(
                name=a.name,
                index=a.index,
                enabled=should_enable,
                obsolete=a.obsolete,
                supported=a.supported,
                vote_behavior=a.vote_behavior,
                retired=a.retired,
            )
        )
    return result


# ---------------------------------------------------------------------------
# Profile-based loading
# ---------------------------------------------------------------------------


def get_amendments_for_profile(
    profile: AmendmentProfile | str = AmendmentProfile.RELEASE,
    source: str | Path | None = None,
    enable: list[str] | None = None,
    disable: list[str] | None = None,
) -> list[Amendment]:
    """Load amendments according to the given profile with optional overrides.

    Args:
        profile: "release", "develop", or "custom".
        source: Path to features.macro (develop) or custom JSON file (custom).
                Ignored for "release".
        enable: Amendment names to force-enable.
        disable: Amendment names to force-disable.
    """
    profile = AmendmentProfile(profile) if isinstance(profile, str) else profile

    if profile == AmendmentProfile.RELEASE:
        amendments = resolve_release_source()
    elif profile == AmendmentProfile.DEVELOP:
        raw = resolve_develop_source(source)
        amendments = apply_develop_profile(raw)
    elif profile == AmendmentProfile.CUSTOM:
        if source is None:
            raise ValueError("custom profile requires --amendment-source pointing to a JSON file")
        amendments = _load_amendments_from_json(Path(source))
    else:
        raise ValueError(f"Unknown profile: {profile}")

    # Apply per-amendment overrides
    if enable or disable:
        enable_set = set(enable or [])
        disable_set = set(disable or [])
        amendments = _apply_overrides(amendments, enable_set, disable_set)

    return amendments


def resolve_release_source() -> list[Amendment]:
    """Resolve release amendments via: mainnet RPC → bundled JSON fallback.

    Returns amendments with enabled status from the source.
    """
    # 1. Try mainnet RPC
    try:
        raw = _fetch_amendments(network="mainnet")
        return _amendments_from_raw_dict(raw)
    except (urllib.error.URLError, OSError, TimeoutError, KeyError):
        pass

    # 2. Fall back to bundled JSON
    if Path(str(DEFAULT_MAINNET_LIST)).exists():
        return _load_amendments_from_json(DEFAULT_MAINNET_LIST)

    raise RuntimeError(
        "Could not load release amendments. Mainnet RPC failed and "
        f"bundled {MAINNET_AMENDMENTS_FILE} not found.\n"
        "Options:\n"
        "  1. Use --amendment-source /path/to/amendments.json\n"
        "  2. Use --amendment-profile develop (auto-fetches from GitHub)"
    )


def _amendments_from_raw_dict(raw: dict) -> list[Amendment]:
    """Convert raw xrpld 'feature' RPC response dict to Amendment list."""
    amendments: list[Amendment] = []
    for am_hash, info in raw.items():
        amendments.append(
            Amendment(
                name=info.get("name", am_hash),
                index=am_hash,
                enabled=bool(info.get("enabled", False)),
                obsolete=bool(info.get("obsolete", False)),
                supported=bool(info.get("supported", True)),
                vote_behavior=info.get("vote_behavior", "DefaultNo"),
                retired=bool(info.get("retired", False)),
            )
        )
    return amendments


def _load_amendments_from_json(path: Path) -> list[Amendment]:
    """Load amendments from a JSON file (hash->info dict format)."""
    data = json.loads(path.resolve().read_text())
    amendments: list[Amendment] = []
    for am_hash, info in data.items():
        amendments.append(
            Amendment(
                name=info.get("name", am_hash),
                index=am_hash,
                enabled=bool(info.get("enabled", False)),
                obsolete=bool(info.get("obsolete", False)),
                supported=bool(info.get("supported", True)),
                vote_behavior=info.get("vote_behavior", "DefaultNo"),
                retired=bool(info.get("retired", False)),
            )
        )
    return amendments


def _apply_overrides(
    amendments: list[Amendment],
    enable: set[str],
    disable: set[str],
) -> list[Amendment]:
    """Force-enable or force-disable specific amendments by name."""
    result = []
    for a in amendments:
        if a.name in enable:
            result.append(
                Amendment(
                    name=a.name,
                    index=a.index,
                    enabled=True,
                    obsolete=a.obsolete,
                    supported=a.supported,
                    vote_behavior=a.vote_behavior,
                    retired=a.retired,
                )
            )
        elif a.name in disable:
            result.append(
                Amendment(
                    name=a.name,
                    index=a.index,
                    enabled=False,
                    obsolete=a.obsolete,
                    supported=a.supported,
                    vote_behavior=a.vote_behavior,
                    retired=a.retired,
                )
            )
        else:
            result.append(a)
    return result


# ---------------------------------------------------------------------------
# Legacy API (backward-compatible with existing callers)
# ---------------------------------------------------------------------------


def _get_amendments_from_file(amendments_file: str) -> dict:
    """Return raw amendment dict from JSON file."""
    return json.loads(Path(amendments_file).resolve().read_text())


def _get_amendments_from_network(network: str | None = None) -> dict:
    """Return raw amendment dict from network by calling xrpld feature method."""
    network = network or DEFAULT_NETWORK
    return _fetch_amendments(network=network)


def _get_amendments(source: str | None = None) -> dict:
    net_source = urlparse(source).scheme in ("http", "https")
    if net_source:
        return _get_amendments_from_network(source)
    else:
        return _get_amendments_from_file(source)


def _fetch_amendments(network: str = DEFAULT_NETWORK, timeout: int = 3) -> dict:
    """Call xrpld 'feature' method."""
    url = network_endpoint[network]
    payload = {"method": "feature"}
    data = json.dumps(payload).encode("utf-8")
    response = urllib.request.urlopen(url, data=data, timeout=timeout)
    res = json.loads(response.read())
    return res["result"]["features"]


def get_amendments(source: str | None = None) -> list[Amendment]:
    """Load amendments from a legacy source (JSON file path or network URL).

    This is the original API — preserved for backward compatibility.
    """
    a = _get_amendments(source)
    ams: list[Amendment] = []
    for am_hash, info in a.items():
        ams.append(
            Amendment(
                name=info.get("name", am_hash),
                index=am_hash,
                enabled=bool(info.get("enabled", False)),
                obsolete=bool(info.get("obsolete", False)),
            )
        )
    return ams


def get_enabled_amendment_hashes(
    source: str | None = None,
    *,
    profile: str | None = None,
    amendment_source: str | None = None,
    enable: list[str] | None = None,
    disable: list[str] | None = None,
) -> list[str]:
    """Return list of enabled amendment hashes.

    If ``profile`` is provided, uses the new profile-based system.
    Otherwise falls back to the legacy ``source`` parameter for
    backward compatibility.
    """
    if profile is not None:
        amendments = get_amendments_for_profile(
            profile=profile,
            source=amendment_source,
            enable=enable,
            disable=disable,
        )
    else:
        amendments = get_amendments(source)
    return _enabled_amendment_hashes(amendments)


def _enabled_amendment_hashes(amendments: Iterable[Amendment]) -> list[str]:
    return [a.index for a in amendments if a.enabled]
