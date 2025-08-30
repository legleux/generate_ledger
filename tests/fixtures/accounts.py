import random
from dataclasses import dataclass

import pytest


@dataclass(frozen=True)
class AccountsCfg:
    n: int = 2
    mode: str = "random"
    # wallet: bool = True

    # def __post_init__(self):
    #     print(f"My field is {self.some_field}")


def _select_accounts(account_vectors, n, *, mode="random", seed=None):
    items = list(account_vectors)
    if n is None or n >= len(items):
        return items
    if mode == "first":
        return items[:n]
    if mode == "random":
        rnd = random.Random(seed)
        return rnd.sample(items, n)
    raise ValueError(f"unknown mode: {mode}")


@pytest.fixture
def accounts_factory(account_vectors):
    def make(n=None, mode=None):
        cfg = AccountsCfg()
        return _select_accounts(account_vectors, n or cfg.n, mode=mode or cfg.mode)

    return make


# @pytest.fixture()
# def setup_account():
#     algorithm = xrpl.CryptoAlgorithm.SECP256K1
#     seed = generate_seed()
#     Wallet.from_seed()
