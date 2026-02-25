import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from pydantic import PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict

from generate_ledger.crypto_backends import Algorithm, get_backend, backend_info


@dataclass
class Account:
    address: str
    seed: str
    algorithm: str = "secp256k1"  # "ed25519" or "secp256k1"

    def __repr__(self):
        return 'Account(%s, %s)' % (self.address, self.seed)

    def __str__(self):
        return '%s, %s' % (self.address, self.seed)

class AccountConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GL_", env_file=".env")
    num_accounts: PositiveInt = 2
    algo: str = "ed25519"  # "ed25519" or "secp256k1"
    balance: str = str(100_000_000000)  # 100k XRP

def generate_accounts(config: AccountConfig | None = None) -> list[Account]:
    """
    Generates n accounts (address + seed).

    Uses native crypto backends when available (PyNaCl for ed25519)
    for ~300x speedup over xrpl-py's pure-Python implementation.
    """
    cfg = config or AccountConfig()
    algo = Algorithm(cfg.algo)
    backend = get_backend(algo)
    _, name = backend_info(algo)
    print(f"Generating {cfg.num_accounts} accounts ({cfg.algo}, backend={name}).")
    out: list[Account] = []
    for _ in range(cfg.num_accounts):
        seed, address = backend.generate_account()
        out.append(Account(address, seed, algorithm=cfg.algo))
    return out


def write_accounts_json(accounts: Iterable[tuple[str, str]], path: Path) -> None:
    data = [(a.address, a.seed) for a in accounts]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
