from xrpl.core.keypairs import generate_seed
from xrpl.wallet import Wallet

from generate_ledger.gen import write_ledger_file

__all__ = [
    "Wallet",
    "generate_seed",
]


def main() -> None:
    write_ledger_file(None)
