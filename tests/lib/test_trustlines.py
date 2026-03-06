"""Tests for gl.trustlines — trustline object generation."""

import pytest
from xrpl import CryptoAlgorithm
from xrpl.wallet import Wallet

from generate_ledger.accounts import Account
from generate_ledger.trustlines import (
    TrustlineConfig,
    TrustlineObjects,
    generate_trustline_objects,
    generate_trustlines,
    generate_trustset_txn_id,
)
from tests.conftest import ALICE_ADDRESS, ALICE_SEED, BOB_ADDRESS, BOB_SEED

# TODO: Constant
TXN_ID_LEN = 64


@pytest.fixture
def alice():
    return Account(ALICE_ADDRESS, ALICE_SEED)


@pytest.fixture
def bob():
    return Account(BOB_ADDRESS, BOB_SEED)


# ---------------------------------------------------------------------------
# TrustlineConfig
# ---------------------------------------------------------------------------
class TestTrustlineConfig:
    def test_defaults(self):
        cfg = TrustlineConfig()
        assert cfg.num_trustlines == 0
        assert cfg.currencies == ["USD", "EUR", "GBP"]
        assert cfg.default_limit == str(int(100e9))
        assert cfg.ledger_seq == 2


# ---------------------------------------------------------------------------
# generate_trustset_txn_id
# ---------------------------------------------------------------------------
class TestGenerateTrustsetTxnId:
    def test_returns_64_hex(self, bob):
        wallet = Wallet.from_seed(bob.seed, algorithm=CryptoAlgorithm.SECP256K1)
        limit_amount = {"currency": "USD", "issuer": ALICE_ADDRESS, "value": "1000000"}
        txn_id = generate_trustset_txn_id(bob, wallet, limit_amount, sequence=4)
        assert len(txn_id) == 64
        assert all(c in "0123456789ABCDEF" for c in txn_id)

    def test_deterministic(self, bob):
        wallet = Wallet.from_seed(bob.seed, algorithm=CryptoAlgorithm.SECP256K1)
        limit_amount = {"currency": "USD", "issuer": ALICE_ADDRESS, "value": "1000000"}
        txn_id1 = generate_trustset_txn_id(bob, wallet, limit_amount, sequence=4)
        txn_id2 = generate_trustset_txn_id(bob, wallet, limit_amount, sequence=4)
        assert txn_id1 == txn_id2

    def test_different_sequences_differ(self, bob):
        wallet = Wallet.from_seed(bob.seed, algorithm=CryptoAlgorithm.SECP256K1)
        limit_amount = {"currency": "USD", "issuer": ALICE_ADDRESS, "value": "1000000"}
        txn_id1 = generate_trustset_txn_id(bob, wallet, limit_amount, sequence=4)
        txn_id2 = generate_trustset_txn_id(bob, wallet, limit_amount, sequence=5)
        assert txn_id1 != txn_id2


# ---------------------------------------------------------------------------
# generate_trustline_objects
# ---------------------------------------------------------------------------
class TestGenerateTrustlineObjects:
    def test_returns_3_objects(self, alice, bob):
        tl = generate_trustline_objects(alice, bob, "USD", 1_000_000_000)
        assert isinstance(tl, TrustlineObjects)
        assert tl.ripple_state is not None
        assert tl.directory_node_a is not None
        assert tl.directory_node_b is not None

    def test_ripple_state_structure(self, alice, bob):
        tl = generate_trustline_objects(alice, bob, "USD", 1_000_000_000)
        rs = tl.ripple_state
        assert rs["LedgerEntryType"] == "RippleState"
        assert rs["Balance"]["currency"] == "USD"
        assert rs["Balance"]["value"] == "0"
        assert rs["Balance"]["issuer"] == "rrrrrrrrrrrrrrrrrrrrBZbvji"
        assert rs["Flags"] == 131072  # lsfLowReserve
        assert len(rs["index"]) == 64

    def test_high_low_ordering(self, alice, bob):
        """HighLimit/LowLimit accounts are ordered lexicographically."""
        tl = generate_trustline_objects(alice, bob, "USD", 1_000_000_000)
        rs = tl.ripple_state
        lo = rs["LowLimit"]["issuer"]
        hi = rs["HighLimit"]["issuer"]
        assert lo.encode() < hi.encode()

    def test_directory_node_structure(self, alice, bob):
        tl = generate_trustline_objects(alice, bob, "USD", 1_000_000_000)
        for dn in [tl.directory_node_a, tl.directory_node_b]:
            assert dn["LedgerEntryType"] == "DirectoryNode"
            assert dn["Flags"] == 0
            assert isinstance(dn["Indexes"], list)
            assert len(dn["Indexes"]) == 1

    def test_directory_nodes_reference_ripple_state_index(self, alice, bob):
        tl = generate_trustline_objects(alice, bob, "USD", 1_000_000_000)
        rsi = tl.ripple_state["index"]
        assert tl.directory_node_a["Indexes"][0] == rsi
        assert tl.directory_node_b["Indexes"][0] == rsi

    def test_owners_match_accounts(self, alice, bob):
        tl = generate_trustline_objects(alice, bob, "USD", 1_000_000_000)
        owners = {tl.directory_node_a["Owner"], tl.directory_node_b["Owner"]}
        assert owners == {alice.address, bob.address}

    def test_previous_txn_id_set(self, alice, bob):
        tl = generate_trustline_objects(alice, bob, "USD", 1_000_000_000)
        txn_id = tl.ripple_state["PreviousTxnID"]
        assert len(txn_id) == TXN_ID_LEN
        assert txn_id == tl.directory_node_a["PreviousTxnID"]
        assert txn_id == tl.directory_node_b["PreviousTxnID"]

    def test_limit_values(self, alice, bob):
        limit = 5_000_000
        tl = generate_trustline_objects(alice, bob, "USD", limit)
        rs = tl.ripple_state
        assert rs["HighLimit"]["value"] == str(limit)
        assert rs["LowLimit"]["value"] == str(limit)


# ---------------------------------------------------------------------------
# generate_trustlines
# ---------------------------------------------------------------------------
class TestGenerateTrustlines:
    def test_zero_trustlines(self, alice, bob):
        cfg = TrustlineConfig(num_trustlines=0)
        result = generate_trustlines([alice, bob], cfg)
        assert result == []

    def test_one_trustline(self, alice, bob):
        cfg = TrustlineConfig(num_trustlines=1, currencies=["USD"])
        result = generate_trustlines([alice, bob], cfg)
        assert len(result) == 1
        assert isinstance(result[0], TrustlineObjects)

    def test_fewer_than_2_accounts_raises(self, alice):
        cfg = TrustlineConfig(num_trustlines=1)
        with pytest.raises(ValueError, match="at least 2 accounts"):
            generate_trustlines([alice], cfg)

    def test_no_duplicate_pairs(self, alice, bob):
        cfg = TrustlineConfig(num_trustlines=10, currencies=["USD"])
        result = generate_trustlines([alice, bob], cfg)
        # With only 2 accounts and 1 currency, max 1 unique pair
        assert len(result) <= 1
