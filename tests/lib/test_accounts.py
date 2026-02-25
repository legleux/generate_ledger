"""Tests for gl.accounts — account generation and JSON export."""
import json

from gl.accounts import Account, AccountConfig, generate_accounts, write_accounts_json
from tests.conftest import ALICE_ADDRESS, ALICE_SEED


class TestAccount:
    def test_repr(self):
        acct = Account(ALICE_ADDRESS, ALICE_SEED)
        assert ALICE_ADDRESS in repr(acct)
        assert ALICE_SEED in repr(acct)

    def test_str(self):
        acct = Account(ALICE_ADDRESS, ALICE_SEED)
        result = str(acct)
        assert ALICE_ADDRESS in result
        assert ALICE_SEED in result

    def test_algorithm_default(self):
        acct = Account("rAddr", "sSeed")
        assert acct.algorithm == "secp256k1"

    def test_algorithm_explicit(self):
        acct = Account("rAddr", "sSeed", algorithm="ed25519")
        assert acct.algorithm == "ed25519"


class TestAccountConfig:
    def test_defaults(self):
        cfg = AccountConfig()
        assert cfg.num_accounts == 2
        assert cfg.algo == "ed25519"
        assert cfg.balance == str(100_000_000000)

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("GL_NUM_ACCOUNTS", "10")
        cfg = AccountConfig()
        assert cfg.num_accounts == 10

    def test_algo_env_override(self, monkeypatch):
        monkeypatch.setenv("GL_ALGO", "secp256k1")
        cfg = AccountConfig()
        assert cfg.algo == "secp256k1"


class TestGenerateAccounts:
    def test_correct_count(self):
        cfg = AccountConfig(num_accounts=3)
        accounts = generate_accounts(cfg)
        assert len(accounts) == 3

    def test_addresses_start_with_r(self):
        cfg = AccountConfig(num_accounts=2)
        accounts = generate_accounts(cfg)
        for acct in accounts:
            assert acct.address.startswith("r")

    def test_seeds_start_with_s(self):
        cfg = AccountConfig(num_accounts=2)
        accounts = generate_accounts(cfg)
        for acct in accounts:
            assert acct.seed.startswith("s")

    def test_unique_addresses(self):
        cfg = AccountConfig(num_accounts=5)
        accounts = generate_accounts(cfg)
        addresses = [a.address for a in accounts]
        assert len(set(addresses)) == 5

    def test_default_config(self):
        accounts = generate_accounts()
        assert len(accounts) == 2  # default num_accounts

    def test_default_algo_is_ed25519(self):
        accounts = generate_accounts(AccountConfig(num_accounts=1))
        assert accounts[0].algorithm == "ed25519"

    def test_secp256k1_fallback(self):
        cfg = AccountConfig(num_accounts=1, algo="secp256k1")
        accounts = generate_accounts(cfg)
        assert accounts[0].algorithm == "secp256k1"
        assert accounts[0].address.startswith("r")
        assert accounts[0].seed.startswith("s")

    def test_ed25519_seed_is_wallet_importable(self):
        """Verify that seeds from the native ed25519 backend can be used
        with xrpl-py's Wallet.from_seed() to recover the same address."""
        from xrpl import CryptoAlgorithm
        from xrpl.wallet import Wallet

        cfg = AccountConfig(num_accounts=3)
        accounts = generate_accounts(cfg)
        for acct in accounts:
            wallet = Wallet.from_seed(acct.seed, algorithm=CryptoAlgorithm.ED25519)
            assert wallet.address == acct.address, (
                f"Wallet address mismatch: {wallet.address} != {acct.address}"
            )


class TestWriteAccountsJson:
    def test_writes_valid_json(self, tmp_path):
        accts = [Account("rAddr1", "sSeed1"), Account("rAddr2", "sSeed2")]
        path = tmp_path / "accounts.json"
        write_accounts_json(accts, path)
        data = json.loads(path.read_text())
        assert len(data) == 2
        assert data[0] == ["rAddr1", "sSeed1"]
        assert data[1] == ["rAddr2", "sSeed2"]

    def test_creates_parent_dirs(self, tmp_path):
        accts = [Account("rAddr", "sSeed")]
        path = tmp_path / "nested" / "dir" / "accounts.json"
        write_accounts_json(accts, path)
        assert path.exists()
