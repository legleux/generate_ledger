import logging
from pathlib import Path

from pydantic import Field, PositiveInt, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedSeq
from ruamel.yaml.scalarstring import DoubleQuotedScalarString as dq

log = logging.getLogger(__name__)

yaml = YAML()
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.preserve_quotes = True
yaml.representer.ignore_aliases = lambda x: True  # disable anchors


def make_flow_list(items):
    seq = CommentedSeq(items)
    seq.fa.set_flow_style()
    return seq


class ComposeConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GL_", env_file=".env")
    default_output_dir: str = "testnet"
    docker_compose_yml: str = "docker-compose.yml"
    base_dir: Path = Field(default=Path(default_output_dir))  # Override with env var GL_BASE_DIR
    num_validators: PositiveInt = 5
    validator_name: str = "val"
    validator_image_tag: str = "develop"
    validator_image: str = "rippleci/xrpld"
    num_hubs: PositiveInt = 1
    hub_name: str = "xrpld"
    hub_image: str = "rippleci/xrpld"
    hub_image_tag: str = "develop"
    # where outputs land by default (env var GL_BASE_DIR overrides)
    # base_dir: Path = Field(default=Path(".gl"))

    @computed_field
    @property
    def compose_yml(self) -> Path:
        return self.base_dir / self.docker_compose_yml

    network_name: str = "xrpl_net"
    rpc_port: int = 5005
    ws_port: int = 6006
    standalone: bool = False

    ledger_file: str = "/ledger.json"  # REVIEW: Should this live here? What is the path?
    first_validator: str = f"{validator_name}0"


def gen_compose_data(config: ComposeConfig | None = None):
    cfg = config or ComposeConfig()
    # debug log
    # print(f"generating {cfg.num_validators} validators")
    entrypoint_cmd = "xrpld"

    load_command = {"command": make_flow_list([dq("--ledgerfile"), dq(cfg.ledger_file)])}
    net_command = {"command": make_flow_list([dq("--net")])}
    entrypoint = {"entrypoint": make_flow_list([dq(f"{entrypoint_cmd}")])}
    # TODO: Image default entrypoint should already be "xrpld"
    hub_entrypoint = validator_entrypoint = entrypoint
    expose_hub_ports = True
    ### Try a simpler healthcheck
    # healthcheck = {
    #     "healthcheck": {
    #         "test": make_flow_list([dq("CMD"), dq("/usr/bin/curl"), dq("--insecure"), dq(healthcheck_url)]),
    #         "start_period": healthcheck_data["start_period"],
    #         "interval": healthcheck_data["interval"],
    #     }
    # }
    healthcheck = {
        "healthcheck": {
            "test": make_flow_list([dq("CMD"), dq("xrpld"), dq("--silent"), dq("ping")]),
            "start_period": "10s",
            "interval": "10s",
        }
    }
    # hub_healthcheck = {
    #     "healthcheck": {
    #         "test": make_flow_list([dq("CMD"), dq("/usr/bin/curl"), dq("--insecure"), dq(healthcheck_url)]),
    #         "start_period": healthcheck_data["start_period"],
    #         "interval": healthcheck_data["interval"],
    #     }
    # }
    depends_on = {"depends_on": {f"{cfg.first_validator}": {"condition": "service_healthy"}}}
    # depends_on = {"depends_on": make_flow_list([dq(f"{cfg.first_validator}")])}
    # depends_on = {
    #     "depends_on": "val0"}

    compose_data = {}

    # TODO: What to do about this?
    # if include_services is not None:
    #     compose_data.update(include=include_services)
    """ FIXME: This is just a mess. We may want to expose ports of multiple nodes not just the first one.
        It might be worth it to break hubs/vals into separate compose files from templates then just
        include them together.
    """
    validators = {
        (name := f"{cfg.validator_name}{i}"): {
            "image": f"{cfg.validator_image}:{cfg.validator_image_tag}",
            "container_name": f"{name}",
            "hostname": f"{name}",
            **(validator_entrypoint),
            **(
                {
                    "ports": [
                        f"{cfg.rpc_port + i + cfg.num_hubs}:{cfg.rpc_port}",
                        f"{cfg.ws_port + i + cfg.num_hubs}:{cfg.ws_port}",
                    ]
                }
                if name == cfg.first_validator
                else {}
            ),
            # **(load_command),
            **(load_command if name == cfg.first_validator else net_command),
            **(healthcheck if name == cfg.first_validator else depends_on),
            # FIXME: volume mount kind of ugly...
            "volumes": [
                f"./volumes/{name}:/etc/opt/ripple",
                # TODO: Only loading the ledger file if it's the first validator? Test with
                # *([f"./{cfg.ledger_file}:/{cfg.ledger_file}"] if i == 0 else [])
                *([f".{cfg.ledger_file}:{cfg.ledger_file}"]),
                # "./ledger.json:/ledger.json" if i == 0 else None,
            ],
            "networks": [cfg.network_name],
        }
        for i in range(cfg.num_validators)
    }

    hubs = {
        (name := f"{cfg.hub_name}{(i if cfg.num_hubs > 1 else '')}"): {
            "image": f"{cfg.hub_image}:{cfg.hub_image_tag}",
            "container_name": f"{name}",
            "hostname": f"{name}",
            **(hub_entrypoint),
            **(
                {
                    "ports": [
                        f"{(cfg.rpc_port + i)}:{cfg.rpc_port}",
                        f"{cfg.ws_port + i}:{cfg.ws_port}",
                    ]
                }
                if expose_hub_ports
                else {}
            ),
            **(depends_on),
            # FIXME: volume mount kind of ugly...
            "volumes": [
                f"./volumes/{name}:/etc/opt/ripple",
                # TODO: Only loading the ledger file if it's the first hub? Test with
                # *([f"./{cfg.ledger_file}:/{cfg.ledger_file}"] if i == 0 else [])
                # "./ledger.json:/ledger.json" if i == 0 else None,
            ],
            "networks": [cfg.network_name],
        }
        for i in range(cfg.num_hubs)
    }

    networks = {
        cfg.network_name: {"name": cfg.network_name},
    }

    compose_data.update(services={**validators, **hubs})
    compose_data.update(networks=networks)

    return compose_data


def write_compose_file(output_file: Path | None = None, config: ComposeConfig | None = None) -> Path:
    cfg = config or ComposeConfig()
    output_file = Path(output_file) if output_file else cfg.compose_yml
    output_file.parent.mkdir(exist_ok=True, parents=True)
    log.info("Writing %s to %s", cfg.compose_yml.name, output_file.resolve())
    # yaml.dump(gen_compose_data(cfg), output_file.open("w"))
    # return output_file
    with output_file.open("w") as f:
        yaml.dump(gen_compose_data(cfg), f)
    return output_file
