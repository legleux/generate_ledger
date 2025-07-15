import sys
from xrpl.core.keypairs import generate_seed
from xrpl.wallet import Wallet

from generate_ledger.gen import write_ledger_file
from generate_ledger.compose import main as compose_main
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
