import logging
import subprocess
import tomllib
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import xrpl
from pydantic import BaseModel, Field, model_validator

log = logging.getLogger(__name__)

# ---------- Type aliases ----------

type PublicKey = str
type ValidatorToken = str
type KeygenFn = Callable[[], tuple[PublicKey, ValidatorToken]]

# ---------- TOML layer utilities ----------


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, override_value in override.items():
        base_value = result.get(key)
        if isinstance(base_value, dict) and isinstance(override_value, dict):
            result[key] = deep_merge(base_value, override_value)
        else:
            result[key] = override_value
    return result


def load_toml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("rb") as f:
        return tomllib.load(f) or {}


def load_layers(paths: list[Path]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for path in paths:
        merged = deep_merge(merged, load_toml_file(path))
    return merged


# ---------- Pydantic config models ----------


class NodeRole(StrEnum):
    VALIDATOR = "validator"
    NODE = "node"


class ServerConfig(BaseModel):
    node_size: str = "huge"
    peer_port: int = 2459
    rpc_admin_port: int = 5005
    ws_admin_port: int = 6006


class StorageConfig(BaseModel):
    db_path: str = "/var/lib/xrpld/db"
    db_type: str = "NuDB"
    nudb_path: str = "/var/lib/xrpld/db/nudb"


class RpcConfig(BaseModel):
    admin_bind: str = "0.0.0.0"
    admin_allow: list[str] = Field(default_factory=lambda: ["0.0.0.0"])


class ValidatorModelConfig(BaseModel):
    enabled: bool = False
    token: str | None = None


class VotingConfig(BaseModel):
    reference_fee: int = 10
    account_reserve: int = int(0.2 * 1e6)
    owner_reserve: int = int(1.0 * 1e6)


class FeaturesConfig(BaseModel):
    amendments: list[str] = Field(default_factory=list)
    majority_time: str | None = None


class LoggingConfig(BaseModel):
    level: str = "info"
    file: str = "/var/log/xrpld/debug.log"

    VALID_LEVELS: frozenset[str] = frozenset({"trace", "debug", "info", "warning", "error", "fatal"})

    model_config = {"arbitrary_types_allowed": True}

    @model_validator(mode="after")
    def validate_level(self) -> "LoggingConfig":
        if self.level not in self.VALID_LEVELS:
            raise ValueError(f"log level must be one of {sorted(self.VALID_LEVELS)}, got '{self.level}'")
        return self


class NetworkConfig(BaseModel):
    chain: str = "main"
    peers_max: int = 64
    ips_fixed: list[str] = Field(default_factory=list)
    validator_pubkeys: list[str] = Field(default_factory=list)


class XrpldNodeConfig(BaseModel):
    role: NodeRole
    server: ServerConfig = Field(default_factory=ServerConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    rpc: RpcConfig = Field(default_factory=RpcConfig)
    validator: ValidatorModelConfig = Field(default_factory=ValidatorModelConfig)
    voting: VotingConfig = Field(default_factory=VotingConfig)
    features: FeaturesConfig = Field(default_factory=FeaturesConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    network: NetworkConfig = Field(default_factory=NetworkConfig)

    @model_validator(mode="after")
    def validate_role_rules(self) -> "XrpldNodeConfig":
        match self.role:
            case NodeRole.VALIDATOR:
                if not self.validator.enabled:
                    raise ValueError("validator role requires validator.enabled = true")
                if not self.validator.token:
                    raise ValueError("validator role requires validator.token")
            case NodeRole.NODE:
                if self.validator.enabled:
                    raise ValueError("node role cannot enable validator mode")
        return self


# ---------- Section model + generators ----------


@dataclass(slots=True)
class Section:
    name: str
    lines: list[str]


def gen_server(cfg: XrpldNodeConfig) -> Section:
    return Section("server", ["port_rpc_admin_local", "port_peer", "port_ws_admin_local"])


def gen_port_rpc_admin_local(cfg: XrpldNodeConfig) -> Section:
    return Section(
        "port_rpc_admin_local",
        [
            f"port = {cfg.server.rpc_admin_port}",
            f"ip = {cfg.rpc.admin_bind}",
            f"admin = [{','.join(cfg.rpc.admin_allow)}]",
            "protocol = http",
        ],
    )


def gen_port_peer(cfg: XrpldNodeConfig) -> Section:
    return Section(
        "port_peer",
        [
            f"port = {cfg.server.peer_port}",
            f"ip = {cfg.rpc.admin_bind}",
            "protocol = peer",
        ],
    )


def gen_port_ws_admin_local(cfg: XrpldNodeConfig) -> Section:
    return Section(
        "port_ws_admin_local",
        [
            f"port = {cfg.server.ws_admin_port}",
            f"ip = {cfg.rpc.admin_bind}",
            f"admin = [{','.join(cfg.rpc.admin_allow)}]",
            "protocol = ws",
            "send_queue_limit = 500",
        ],
    )


def gen_node_db(cfg: XrpldNodeConfig) -> Section:
    return Section("node_db", [f"type = {cfg.storage.db_type}", f"path = {cfg.storage.nudb_path}"])


def gen_ledger_history(cfg: XrpldNodeConfig) -> Section | None:
    if cfg.role is NodeRole.VALIDATOR:
        return None
    return Section("ledger_history", ["full"])


def gen_database_path(cfg: XrpldNodeConfig) -> Section:
    return Section("database_path", [cfg.storage.db_path])


def gen_debug_logfile(cfg: XrpldNodeConfig) -> Section:
    return Section("debug_logfile", [cfg.logging.file])


def gen_node_size(cfg: XrpldNodeConfig) -> Section:
    return Section("node_size", [cfg.server.node_size])


def gen_rpc_startup(cfg: XrpldNodeConfig) -> Section:
    return Section("rpc_startup", [f'{{ "command": "log_level", "severity": "{cfg.logging.level}" }}'])


def gen_ips_fixed(cfg: XrpldNodeConfig) -> Section | None:
    if not cfg.network.ips_fixed:
        return None
    return Section("ips_fixed", list(cfg.network.ips_fixed))


def gen_validators(cfg: XrpldNodeConfig) -> Section | None:
    if not cfg.network.validator_pubkeys:
        return None
    return Section("validators", list(cfg.network.validator_pubkeys))


def gen_voting(cfg: XrpldNodeConfig) -> Section | None:
    if cfg.role is not NodeRole.VALIDATOR:
        return None
    return Section(
        "voting",
        [
            f"reference_fee = {cfg.voting.reference_fee}",
            f"account_reserve = {cfg.voting.account_reserve}",
            f"owner_reserve = {cfg.voting.owner_reserve}",
        ],
    )


def gen_features(cfg: XrpldNodeConfig) -> Section | None:
    if not cfg.features.amendments:
        return None
    return Section("features", list(cfg.features.amendments))


def gen_amendment_majority_time(cfg: XrpldNodeConfig) -> Section | None:
    if not cfg.features.majority_time:
        return None
    return Section("amendment_majority_time", [cfg.features.majority_time])


def gen_validation_seed(cfg: XrpldNodeConfig) -> Section | None:
    if cfg.role is not NodeRole.VALIDATOR or not cfg.validator.token:
        return None
    # token is formatted as "[validation_seed]\nseed" — split into name + lines
    token_lines = cfg.validator.token.split("\n")
    # First line is "[validation_seed]", rest are the seed values
    return Section("validation_seed", token_lines[1:])


SECTION_GENERATORS: list[Callable[[XrpldNodeConfig], Section | None]] = [
    gen_server,
    gen_port_rpc_admin_local,
    gen_port_peer,
    gen_port_ws_admin_local,
    gen_node_db,
    gen_ledger_history,
    gen_database_path,
    gen_debug_logfile,
    gen_node_size,
    lambda cfg: Section("beta_rpc_api", ["1"]),
    gen_rpc_startup,
    lambda cfg: Section("ssl_verify", ["0"]),
    lambda cfg: Section("compression", ["0"]),
    lambda cfg: Section("peer_private", ["0"]),
    lambda cfg: Section("signing_support", ["false"]),
    gen_ips_fixed,
    gen_validators,
    gen_voting,
    gen_features,
    gen_amendment_majority_time,
    gen_validation_seed,
]


# ---------- Renderer ----------


def build_sections(cfg: XrpldNodeConfig) -> list[Section]:
    sections: list[Section] = []
    for generator in SECTION_GENERATORS:
        section = generator(cfg)
        if section is not None:
            sections.append(section)
    return sections


def render_sections(sections: Iterable[Section]) -> str:
    parts: list[str] = []
    for section in sections:
        parts.append(f"[{section.name}]")
        parts.extend(section.lines)
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def render_xrpld_cfg(cfg: XrpldNodeConfig) -> str:
    return render_sections(build_sections(cfg))


# ---------- TOML layer-based config builder ----------

_CONFIG_DIR = Path(__file__).parent.resolve() / "config"


def load_config_layers(
    config_dir: Path = _CONFIG_DIR,
    *,
    env: str | None = None,
    role: str = "node",
    host: str | None = None,
) -> dict[str, Any]:
    layer_paths = [config_dir / "base.toml"]
    if env:
        layer_paths.append(config_dir / "envs" / f"{env}.toml")
    layer_paths.append(config_dir / "roles" / f"{role}.toml")
    if host:
        layer_paths.append(config_dir / "hosts" / f"{host}.toml")
    merged = load_layers(layer_paths)
    merged["role"] = role
    return merged


def build_config(
    config_dir: Path = _CONFIG_DIR,
    *,
    env: str | None = None,
    role: str = "node",
    host: str | None = None,
) -> XrpldNodeConfig:
    merged = load_config_layers(config_dir, env=env, role=role, host=host)
    return XrpldNodeConfig.model_validate(merged)


# ---------- Key generation strategies ----------


def keygen_xrpl() -> tuple[str, str]:
    seed = xrpl.core.keypairs.generate_seed(algorithm=xrpl.CryptoAlgorithm.SECP256K1)
    pub_hex, _ = xrpl.core.keypairs.derive_keypair(seed, validator=True)
    token = f"[validation_seed]\n{seed}"
    pub_key = xrpl.core.addresscodec.encode_node_public_key(bytes.fromhex(pub_hex))
    return pub_key, token


def keygen_docker(cmd: Iterable[str] = ("docker", "run", "legleux/vkt")) -> tuple[str, str]:
    res = subprocess.run(list(cmd), capture_output=True, text=True, check=True)
    public_key_string, token, *_ = res.stdout.split("\n\n")
    pub_key = public_key_string.split()[-1]
    return pub_key, token


# ---------- Result types ----------


@dataclass(slots=True)
class NodeConfig:
    name: str
    is_validator: bool
    config_text: str


@dataclass(slots=True)
class BuildResult:
    nodes: list[NodeConfig]
    validator_pubkeys: list[str]


@dataclass(slots=True)
class WriteResult:
    paths: list[Path]
    validator_pubkeys: list[str]


# ---------- XrpldConfigSpec ----------


@dataclass(slots=True)
class XrpldConfigSpec:
    # topology / naming
    num_validators: int = 5
    validator_name: str = "val"
    xrpld_name: str = "xrpld"
    base_dir: Path = Path("testnet/volumes")

    # key generation strategy
    keygen: Callable[[], tuple[str, str]] = staticmethod(keygen_xrpl)  # noqa: RUF009

    # overrides applied on top of TOML layers
    features: list[str] | None = None
    amendment_majority_time: str | None = None
    log_level: str | None = None
    reference_fee: int | None = None
    account_reserve: int | None = None
    owner_reserve: int | None = None

    # TOML layer directory (defaults to bundled config/)
    config_dir: Path = _CONFIG_DIR
    env: str | None = None

    def _label(self, i: int) -> str:
        width = len(str(self.num_validators - 1)) if self.num_validators > 9 else 1  # noqa: PLR2004
        return f"{self.validator_name}{i:0{width}d}"

    def _ips_fixed(self, exclude_index: int | None, peer_port: int) -> list[str]:
        return [
            f"{self._label(j)} {peer_port}"
            for j in range(self.num_validators)
            if exclude_index is None or j != exclude_index
        ]

    def _build_node_config(self, role: str, **extra: Any) -> XrpldNodeConfig:
        merged = load_config_layers(self.config_dir, env=self.env, role=role)
        # Apply CLI/programmatic overrides onto raw dict before validation
        if self.log_level is not None:
            merged.setdefault("logging", {})["level"] = self.log_level
        if self.features is not None:
            merged.setdefault("features", {})["amendments"] = self.features
        if self.amendment_majority_time is not None:
            merged.setdefault("features", {})["majority_time"] = self.amendment_majority_time
        if self.reference_fee is not None:
            merged.setdefault("voting", {})["reference_fee"] = self.reference_fee
        if self.account_reserve is not None:
            merged.setdefault("voting", {})["account_reserve"] = self.account_reserve
        if self.owner_reserve is not None:
            merged.setdefault("voting", {})["owner_reserve"] = self.owner_reserve
        merged = deep_merge(merged, extra)
        return XrpldNodeConfig.model_validate(merged)

    def build(self) -> BuildResult:
        if self.num_validators < 0:
            raise ValueError("num_validators must be >= 0")

        keys = [self.keygen() for _ in range(self.num_validators)]
        pubkeys = [pk for pk, _ in keys]

        # Load base config from TOML layers to get peer_port
        base_cfg = self._build_node_config("node")
        peer_port = base_cfg.server.peer_port

        nodes: list[NodeConfig] = []

        for i in range(self.num_validators):
            cfg = self._build_node_config(
                "validator",
                validator={"enabled": True, "token": keys[i][1]},
                network={
                    "ips_fixed": self._ips_fixed(exclude_index=i, peer_port=peer_port),
                    "validator_pubkeys": list(pubkeys),
                },
            )
            nodes.append(
                NodeConfig(
                    name=self._label(i),
                    is_validator=True,
                    config_text=render_xrpld_cfg(cfg),
                )
            )

        # non-validator node
        node_cfg = self._build_node_config(
            "node",
            network={
                "ips_fixed": self._ips_fixed(exclude_index=None, peer_port=peer_port),
                "validator_pubkeys": list(pubkeys),
            },
        )
        nodes.append(
            NodeConfig(
                name=self.xrpld_name,
                is_validator=False,
                config_text=render_xrpld_cfg(node_cfg),
            )
        )

        return BuildResult(nodes=nodes, validator_pubkeys=pubkeys)

    def write(self) -> WriteResult:
        result = self.build()
        written: list[Path] = []
        log.info("Writing xrpld configs to %s", self.base_dir.resolve())

        for node in result.nodes:
            out_dir = self.base_dir / node.name
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / "xrpld.cfg"
            out_file.write_text(node.config_text, encoding="utf-8")
            written.append(out_file)

        return WriteResult(paths=written, validator_pubkeys=result.validator_pubkeys)


if __name__ == "__main__":
    spec = XrpldConfigSpec(num_validators=5)
    out = spec.write()
    print("Wrote:", *map(str, out.paths), sep="\n- ")
