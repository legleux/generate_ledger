from dataclasses import dataclass
from enum import StrEnum
from ruamel.yaml import YAML
from pathlib import Path
import os

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

num_validators = int(os.environ.get("NUM_VALIDATORS", 5))
validator_name = os.environ.get("VALIDATOR_NAME", "val")
rippled_name = os.environ.get("RIPPLED_NAME", "rippled")
first_validator = f"{validator_name}0"

network_name = "antithesis_net"
ledger_file = "ledger.json"
image = "rippled:latest"
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

port = {
    "rpc": 5005,
    "ws": 6006,
}

compose_data = {
    "services": {
        (name:=rippled_name if i >= num_validators else f"{validator_name}{i}"): {
        # f"val{i}": {
            "image": image,
            "container_name": f"{name}",
            "hostname": f"{name}",
            **(entrypoint),
            **({"ports": [f'{port["ws"]}:{port["ws"]}']} if i >= num_validators else {}),
            **(load_command if name == first_validator else net_command),
            **(healthcheck if name == first_validator else depends_on),
            "volumes": [
                f"./volumes/{name}:/etc/opt/ripple",
                *([f"./{ledger_file}:/{ledger_file}"] if i == 0 else [])
                # "./ledger.json:/ledger.json" if i == 0 else None,
            ],
            "networks": [network_name]
        }
        for i in range(num_validators + 1 )
    },
    "networks": {
        network_name : {
            "name": network_name
        },
    },
}

def main():
    test_net_dir = Path("test_network")
    compose_yml = test_net_dir / "docker-compose.yml"
    test_net_dir.mkdir(exist_ok=True, parents=True)
    print(f"writing {compose_yml.resolve()}")
    with compose_yml.open("w") as f:
        yaml.dump(compose_data, f)

if __name__ == "__main__":
    main()

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
