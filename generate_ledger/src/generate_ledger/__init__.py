from xrpl.core.keypairs import generate_seed
from xrpl.wallet import Wallet

from generate_ledger.gen import write_ledger_file
from generate_ledger.compose import main
__all__ = [
    "Wallet",
    "generate_seed",
]


def compose():
    main()

def ledger():
    write_ledger_file()
