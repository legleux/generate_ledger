import sys
from generate_ledger.gen import write_ledger_file
from generate_ledger.compose import generate_compose_file
from generate_ledger.rippled_config import generate_config
import click
import os
from platformdirs import user_config_path
from generate_ledger.utils import get_config_file
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("generate-ledger")
    __name__ = "generate_ledger"
except PackageNotFoundError:
    __version__ = "0.0.0"
cfg_path = get_config_file("generate_ledger")
# print("Config will live at:", cfg_path)

# This gives you the right base path for configs on Linux/macOS/Windows
# config_path = user_config_path("myapp", appauthor=False) / "config.yaml"

DEFAULT_NUM_VALIDATORS = 5
DEFAULT_NUM_ACCOUNTS   = 20
DEFAULT_NUM_VALIDATORS = os.environ.get("NUM_VALIDATORS", DEFAULT_NUM_VALIDATORS)
DEFAULT_NUM_ACCOUNTS   = os.environ.get("NUM_ACCOUNTS", DEFAULT_NUM_ACCOUNTS)
DEFAULT_NETWORK_NAME   = os.environ.get("NETWORK_NAME", "xrpld_net")

def compose(num_validators, network_name, include_services):
    # print("Generating compose.yml")
    generate_compose_file(num_validators, network_name, include_services)
    # print("Generated compose.yml")

def ledger(num_accounts):
    # print("Generating ledger.json")
    write_ledger_file(num_accounts)

def config():
    # print("Generating rippled.cfg")
    generate_config()

def xrp_art():
    import zlib, pathlib
    # TODO: How to get this into the installation location?
    print(zlib.decompress(pathlib.Path("art.bin").read_bytes()).decode(encoding='utf-8'))

@click.command(context_settings=dict(
               help_option_names=["-h", "--help"],
               show_default=True))
@click.option("-n", "--network_name",
              default=DEFAULT_NETWORK_NAME,
              help="Sets the network name.",
              type=str,
              )
@click.option("-v", "--num_validators",
              default=DEFAULT_NUM_VALIDATORS,
              help="How many validators to create.",
              type=int,
              )
@click.option("-s", "--include_services",
              help="Include additional compose files in docker-compose.yml.",
              multiple=True,
              )
@click.option("-a", "--num_accounts",
              default=DEFAULT_NUM_ACCOUNTS,
              help="How many accounts to create for the initial ledger.",
              type=int,
              )
@click.option("--config_only",
              help="Do not create an initial ledger, use the genesis ledger.",
              is_flag=True,
              )
@click.option("--art",
              is_flag=True,
              default=False,
              )
def main(num_validators, network_name, include_services, num_accounts, config_only, art):
    """Ledger Tools"""
    if art:
        pass # xrp_art() # dump art and exit
    else:
        compose(num_validators, network_name, include_services)
        generate_config(num_validators)
        if not config_only:
            write_ledger_file(num_accounts)
