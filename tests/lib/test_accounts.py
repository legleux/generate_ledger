"""Tests for gl.accounts — account generation and JSON export."""
import json

import pytest
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


class TestAccountConfig:
    def test_defaults(self):
        cfg = AccountConfig()
        assert cfg.num_accounts == 2
        assert cfg.balance == str(100_000_000000)

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("GL_NUM_ACCOUNTS", "10")
        cfg = AccountConfig()
        assert cfg.num_accounts == 10


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
