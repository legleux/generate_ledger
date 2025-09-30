from dataclasses import dataclass
from typing import Iterable
import urllib.request
import json
from pathlib import Path
from urllib.parse import urlparse
from gl import data_dir

network_endpoint = {
    "devnet": "https://s.devnet.rippletest.net:51234",
    "testnet": "https://s.altnet.rippletest.net:51234",
    "mainnet": "https://s1.ripple.com:51234",
}

DEFAULT_NETWORK = "devnet"
DEFAULT_AMENDMENT_LIST = data_dir / "amendment_list_dev_20250907.json"


@dataclass(frozen=True, slots=True)
class Amendment:
    name: str
    index: str
    enabled: bool
    obsolete: bool = False

def _get_amendments_from_file(amendments_file: str | None = None) -> list[Amendment]:
    """Return list of amendments from file as rippled feature list"""
    if amendments_file is not None:
        features_file = Path(amendments_file)
    else:
        features_file = DEFAULT_AMENDMENT_LIST
    return json.loads(features_file.resolve().read_text())

def _get_amendments_from_network(network: str | None = None)-> list[Amendment]:
    """Return list of amendments from network by claling rippled feature method"""
    network = network or DEFAULT_NETWORK
    return _fetch_amendments(network=network)

def _get_amendments(source: str | None = None)-> list[Amendment]:
    net_source = urlparse(source).scheme in ("http", "https")
    if net_source:
        return _get_amendments_from_network(source)
    else:
        return _get_amendments_from_file(source)

def _fetch_amendments(network: str = DEFAULT_NETWORK, timeout: int = 3) -> list[Amendment]:
    """Call rippled 'feature' method."""
    url = network_endpoint[network]
    payload = {"method": "feature"}
    data = json.dumps(payload).encode("utf-8")
    response = urllib.request.urlopen(url, data=data, timeout=timeout)
    res = json.loads(response.read())
    amend = res["result"]["features"]
    return amend

def get_amendments(source: str | None = None) -> list[Amendment]:
    """
    Accepts: source to read amendments from.
    Returns: list[Amendment]
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

def get_enabled_amendment_hashes(source: str | None = None) -> list[str]:
    a = get_amendments(source)
    return _enabled_amendment_hashes(a)

def _enabled_amendment_hashes(amendments: Iterable[Amendment]) -> list[str]:
    return [a.index for a in amendments if a.enabled]
