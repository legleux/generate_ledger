# src/yourproj/__init__.py
from importlib.metadata import PackageNotFoundError, version

# Keep your clean internal name here
_DIST_NAMES = ["generate-ledger", "legleux-generate-ledger"]

for name in _DIST_NAMES:
    try:
        __version__ = version(name)
        break
    except PackageNotFoundError:
        __version__ = "6.6.6+local"

from ._version import version

__version__ = version
from xrpl.core.keypairs import generate_seed
from xrpl.wallet import Wallet

from generate_ledger.compose import main as compose_main
from generate_ledger.gen import write_ledger_file
from generate_ledger.rippled_config import generate_config


def compose():
    print("Generating compose.yml")
    compose_main()


def ledger():
    print("Generating ledger.json")
    write_ledger_file()


def config():
    print("Generating rippled.cfg")
    generate_config()


def main():
    compose()
    write_ledger_file()
    generate_config()
