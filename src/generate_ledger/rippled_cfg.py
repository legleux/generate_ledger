from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Tuple

import subprocess
import xrpl


# ---------- Key generation strategies ----------

PublicKey = str
ValidatorToken = str
KeygenFn = Callable[[], Tuple[PublicKey, ValidatorToken]]


def keygen_xrpl() -> Tuple[PublicKey, ValidatorToken]:
    """Generate a validator public key and token using xrpl library."""
    seed = xrpl.core.keypairs.generate_seed(algorithm=xrpl.CryptoAlgorithm.SECP256K1)
    pub_hex, _ = xrpl.core.keypairs.derive_keypair(seed, validator=True)
    token = f"[validation_seed]\n{seed}"
    pub_key = xrpl.core.addresscodec.encode_node_public_key(bytes.fromhex(pub_hex))
    return pub_key, token


def keygen_docker(cmd: Iterable[str] = ("docker", "run", "legleux/vkt")) -> Tuple[PublicKey, ValidatorToken]:
    """Generate a validator public key and token via external tool (stdout contract)."""
    res = subprocess.run(list(cmd), capture_output=True, text=True, check=True)
    public_key_string, token, *_ = res.stdout.split("\n\n")
    pub_key = public_key_string.split()[-1]
    return pub_key, token


# ---------- Config & generator ----------

@dataclass(slots=True)
class RippledConfigSpec:
    # topology / naming
    num_validators: int = 5
    validator_name: str = "val"       # directories: val0..val{N-1}
    rippled_name: str = "rippled"     # non-validator node
    base_dir: Path = Path("testnet/volumes")

    # networking
    peer_port: int = 51235

    # economics (drops)
    reference_fee: int = 10                    # 10 drops
    account_reserve: int = int(0.2 * 1e6)      # 0.2 XRP
    owner_reserve: int = int(1.0 * 1e6)        # 1 XRP
    # template
    template_path: Path = Path(__file__).parent.resolve() / "rippled.cfg"

    # key generation strategy
    keygen: KeygenFn = staticmethod(keygen_xrpl)

    # amendment features to vote for
    features: List[str] | None = None

    # how long before amendments gain majority (e.g. "2 minutes")
    amendment_majority_time: str | None = None

    def validate(self) -> None:
        if self.num_validators < 0:
            raise ValueError("num_validators must be >= 0")
        if not self.template_path.is_file():
            raise FileNotFoundError(f"Template not found: {self.template_path}")

    # ---- content helpers ----

    def voting_block(self) -> str:
        return (
            "\n[voting]\n"
            f"reference_fee = {self.reference_fee}\n"
            f"account_reserve = {self.account_reserve}\n"
            f"owner_reserve = {self.owner_reserve}\n\n"
        )

    def features_block(self) -> str:
        if not self.features:
            return ""
        lines = "\n".join(self.features)
        return f"\n[features]\n{lines}\n"

    def amendment_majority_time_block(self) -> str:
        if not self.amendment_majority_time:
            return ""
        return f"\n[amendment_majority_time]\n{self.amendment_majority_time}\n"

    def ips_fixed_block(self, who_index: int | None) -> str:
        """
        Build [ips_fixed].
        - For validator i, include all validators except self i.
        - For the rippled (non-validator) node: include all validators.
        """
        lines: List[str] = []
        for j in range(self.num_validators):
            if who_index is not None and j == who_index:
                continue
            lines.append(f"{self.validator_name}{j} {self.peer_port}")
        return "\n[ips_fixed]\n" + "\n".join(lines) + "\n"

    # ---- main generation ----

    def build(self) -> "BuildResult":
        """
        Build all file contents in-memory.
        Returns a summary with per-node config text and key material.
        """
        self.validate()
        template_str = self.template_path.read_text(encoding="utf-8")

        # Generate validator keys/tokens up front
        vt: List[Tuple[PublicKey, ValidatorToken]] = [self.keygen() for _ in range(self.num_validators)]
        validator_pubkeys = "\n[validators]\n" + "\n".join(pk for pk, _ in vt) + "\n"

        nodes: List[NodeConfig] = []

        # validators
        for i in range(self.num_validators):
            cfg = template_str
            cfg += self.ips_fixed_block(who_index=i)
            cfg += validator_pubkeys
            cfg += self.voting_block()
            cfg += self.features_block()
            cfg += self.amendment_majority_time_block()
            cfg += vt[i][1]  # token
            cfg += "\n"

            nodes.append(
                NodeConfig(
                    name=f"{self.validator_name}{i}",
                    is_validator=True,
                    config_text=cfg,
                )
            )

        # non-validator rippled node
        cfg = template_str
        cfg += self.ips_fixed_block(who_index=None)
        cfg += validator_pubkeys
        cfg += self.features_block()
        cfg += self.amendment_majority_time_block()
        cfg += "\n"

        nodes.append(
            NodeConfig(
                name=self.rippled_name,
                is_validator=False,
                config_text=cfg,
            )
        )

        return BuildResult(nodes=nodes, validator_pubkeys=[pk for pk, _ in vt])

    def write(self) -> "WriteResult":
        """
        Write configs to disk under base_dir/{name}/{node_N}.cfg.
        Returns paths written for assertions/tests.
        """
        result = self.build()
        written: List[Path] = []
        print(f"Writing rippled configs to {self.base_dir.resolve()}")

        for node in result.nodes:
            out_dir = self.base_dir / node.name
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / "rippled.cfg"
            out_file.write_text(node.config_text, encoding="utf-8")
            written.append(out_file)

        return WriteResult(paths=written, validator_pubkeys=result.validator_pubkeys)


@dataclass(slots=True)
class NodeConfig:
    name: str
    is_validator: bool
    config_text: str


@dataclass(slots=True)
class BuildResult:
    nodes: List[NodeConfig]
    validator_pubkeys: List[PublicKey]


@dataclass(slots=True)
class WriteResult:
    paths: List[Path]
    validator_pubkeys: List[PublicKey]


if __name__ == "__main__":
    # Minimal, explicit main; easy to swap to Typer/Click later.
    spec = RippledConfigSpec(
        num_validators=5,
        # keygen=keygen_docker,  # uncomment to use docker-based keygen
    )
    out = spec.write()
    print("Wrote:", *map(str, out.paths), sep="\n- ")
