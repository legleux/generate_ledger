from dataclasses import dataclass
from enum import StrEnum
from ruamel.yaml import YAML
from pathlib import Path
import os

import click
from ruamel.yaml.comments import CommentedSeq
from ruamel.yaml.scalarstring import DoubleQuotedScalarString as dq

yaml = YAML()
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.preserve_quotes = True
yaml.representer.ignore_aliases = lambda x: True  # disable anchors

def make_flow_list(items):
    seq = CommentedSeq(items)
    seq.fa.set_flow_style()
    return seq

DEFAULT_NUM_VALIDATORS = 5
DEFAULT_NUM_VALIDATORS = os.environ.get("NUM_VALIDATORS", DEFAULT_NUM_VALIDATORS)
validator_name     = os.environ.get("VALIDATOR_NAME", "val")
rippled_name       = os.environ.get("RIPPLED_NAME", "rippled")
image              = os.environ.get("RIPPLED_IMAGE", "rippled:latest")
# NETWORK_NAME       = os.environ.get("NETWORK_NAME", "xrpld_net")
test_net_dir_name  = os.environ.get("TESTNET_DIR", "testnet")
docker_compose_yml = "docker-compose.yml"
first_validator    = f"{validator_name}0"

ledger_file = "ledger.json"
entrypoint_cmd = "rippled"
load_command = {"command": make_flow_list([dq("--ledgerfile"), dq(ledger_file)])}
net_command = {"command": make_flow_list([dq("--net")])}
entrypoint = {"entrypoint": make_flow_list([dq(f"{entrypoint_cmd}")])}
init = True
healthcheck_data = {
    "host": "localhost",
    "peer_port": "51235",
    "interval": "10s",
    "start_period": "45s"
}
healthcheck_url = f"https://{healthcheck_data['host']}:{healthcheck_data['peer_port']}/health"
healthcheck = {
    "healthcheck": {
        "test": make_flow_list([dq("CMD"), dq("/usr/bin/curl"), dq("--insecure"), dq(healthcheck_url)]),
        "start_period": healthcheck_data["start_period"],
        "interval": healthcheck_data["interval"],
    }
}
depends_on = {
    "depends_on": [f"{first_validator}0"]
}
depends_on = {"depends_on": make_flow_list([dq(f"{first_validator}")])}


def gen_compose_data(num_validators, network_name, include_services):
    print(f"generating {num_validators} validators")
    compose_data = {}

    if include_services is not None:
        compose_data.update(include=include_services)

    port = {
        "rpc": 5005, # TODO: Configurable/template
        "ws": 6006, # TODO: Configurable/template
    }

    services = {
        (name := rippled_name if i >= num_validators else f"{validator_name}{i}"): {
            "image": image,
            "container_name": f"{name}",
            "hostname": f"{name}",
            **(entrypoint),
            **({"ports": [
                f'{port["rpc"]}:{port["rpc"]}',
                f'{port["ws"]}:{port["ws"]}',
                ]} if i >= num_validators else {}),
            **(load_command if name == first_validator else net_command),
            **(healthcheck if name == first_validator else depends_on),
            "volumes": [
                f"./volumes/{name}:/etc/opt/ripple",
                *([f"./{ledger_file}:/{ledger_file}"] if i == 0 else [])
                # "./ledger.json:/ledger.json" if i == 0 else None,
            ],
            "networks": [network_name]
        } for i in range(num_validators + 1)
    }

    networks = {
        network_name : {
            "name": network_name
        },
    }

    compose_data.update(services=services)
    compose_data.update(networks=networks)

    return compose_data

@dataclass
class Config(StrEnum):
    pass

def generate_validator_config():
    services = {
    }
def generate_rippled_config():
    pass
def generate_config():
    pass

def generate_compose_file(num_validators, network_name, include_services=None):
    test_net_dir = Path(test_net_dir_name)
    compose_yml = test_net_dir / docker_compose_yml
    test_net_dir.mkdir(exist_ok=True, parents=True)
    print(f"writing {compose_yml.resolve()}")
    # print(f"{num_validators=}")
    # print(f"{name=}")
    compose_data = gen_compose_data(num_validators, network_name, include_services)
    with compose_yml.open("w") as f:
        yaml.dump(compose_data, f)

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])
DEFAULT_NETWORK_NAME="rippled_net"
@click.command(context_settings=CONTEXT_SETTINGS)
@click.option("-n", "--network_name", default=DEFAULT_NETWORK_NAME, type=str)
@click.option("-v", "--num_validators", default=DEFAULT_NUM_VALIDATORS, type=int)
@click.option("-s", "--include_services", multiple=True)
def gen_compose(num_validators, network_name, include_services):
    generate_compose_file(num_validators, network_name, include_services)

if __name__ == "__main__":
    gen_compose()
