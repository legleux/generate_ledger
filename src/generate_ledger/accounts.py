import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from pydantic import PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict

from generate_ledger import Wallet, generate_seed

from xrpl import CryptoAlgorithm

@dataclass
class Account:
    address: str
    seed: str
    def __repr__(self):
        return 'Account(%s, %s)' % (self.address, self.seed)
    def __str__(self):
        return '%s, %s' % (self.address, self.seed)

class AccountConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GL_", env_file=".env")
    num_accounts: PositiveInt = 2
    algo: CryptoAlgorithm = CryptoAlgorithm.SECP256K1
    balance: str = str(100_000_000000)  # 100k XRP
    # flags ?

def generate_accounts(config: AccountConfig | None = None) -> list[Account]:
    """
    Generates n accounts (address + seed).
    """
    cfg = config or AccountConfig()
    print(f"Generating {cfg.num_accounts} accounts.")
    out: list[Account] = []
    for _ in range(cfg.num_accounts):
        seed = generate_seed(algorithm=cfg.algo)
        wallet = Wallet.from_seed(seed, algorithm=cfg.algo)
        out.append(Account(wallet.address, seed))
    return out


def write_accounts_json(accounts: Iterable[tuple[str, str]], path: Path) -> None:
    data = [(a.address, a.seed) for a in accounts]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
