import subprocess
from pathlib import Path
import xrpl

num_validators = 5
peer_port = 51235
validator_name = "val"
rippled_name = "rippled"
config_template = Path(__file__).parent.resolve() / "rippled.cfg"
testnet_path = "testnet"
reference_fee = 10               # 10 drops
account_reserve = int(0.2 * 1e6) # 0.2 XRP
owner_reserve = int(1 * 1e6)     # 1 XRP

def generate_public_key():
    seed = xrpl.core.keypairs.generate_seed(algorithm=xrpl.CryptoAlgorithm.SECP256K1)
    pkey, _ = xrpl.core.keypairs.derive_keypair(seed, validator=True)
    seed = f"[validation_seed]\n{seed}"
    return xrpl.core.addresscodec.encode_node_public_key(bytes.fromhex(pkey)), seed

def generate_public_key_():
    generate_validator_key_command = "docker run legleux/vkt".split()
    result = subprocess.run(generate_validator_key_command, capture_output=True, text=True)
    public_key_string, token, *_ = result.stdout.split("\n\n")
    public_key = public_key_string.split(" ")[-1]
    return public_key, token

def gen_voting():
    voting_cfg = (
        "\n[voting]\n" +
        f"reference_fee = {reference_fee}\n"
        f"account_reserve = {account_reserve}\n"
        f"owner_reserve = {owner_reserve}\n"
        "\n"
    )
    return voting_cfg

def generate_config(num_validators):
    # print(f"Looking for config template at: {config_template}")
    rippled_cfg_template_str = Path(config_template).read_text()
    validators = [ generate_public_key() for _ in range(num_validators)]
    validator_public_keys = (
        "\n[validators]\n" +
        "\n".join([pk for pk, _ in validators]) +
        "\n"
    )
    for i in range(num_validators + 1):
        config_dir = f"{validator_name}{i}" if i < num_validators else rippled_name
        config_path = Path(f"{testnet_path}/volumes/{config_dir}")
        config_path.mkdir(exist_ok=True, parents=True)
        config_file_path = config_path / "rippled.cfg"

        if i < num_validators:
            validator_info = validators[i][1]

        ips = (
            "\n[ips_fixed]\n" +
            "\n".join([f"{validator_name}{j} {peer_port}"
                for j in range(num_validators) if i != j or i > num_validators]) + "\n"
        )

        with config_file_path.open("w", encoding="utf-8") as f:
            f.writelines(rippled_cfg_template_str)
            f.writelines(ips)
            f.writelines(validator_public_keys)
            if i < num_validators:
                f.writelines(gen_voting())
                f.writelines(validator_info)
            f.writelines("\n")

if __name__ == "__main__":
    generate_config()
