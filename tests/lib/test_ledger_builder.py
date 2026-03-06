"""Tests for generate_ledger.ledger_builder — ledger assembly."""

import pytest

from generate_ledger.accounts import Account
from generate_ledger.indices import account_root_index
from generate_ledger.ledger_builder import (
    GENESIS_ADDRESS,
    LSF_DEFAULT_RIPPLE,
    TOTAL_COINS_DROPS,
    account_root_entry,
    amendments_to_ledger_entry,
    assemble_ledger_json,
)
from generate_ledger.trustlines import generate_trustline_objects
from tests.conftest import (
    ALICE_ADDRESS,
    ALICE_INDEX,
    ALICE_SEED,
    AMENDMENTS_INDEX,
    BOB_ADDRESS,
    BOB_SEED,
)


@pytest.fixture
def alice():
    return Account(ALICE_ADDRESS, ALICE_SEED)


@pytest.fixture
def bob():
    return Account(BOB_ADDRESS, BOB_SEED)


@pytest.fixture
def sample_hashes():
    return ["AAAA" * 16, "BBBB" * 16]


# ---------------------------------------------------------------------------
# amendments_to_ledger_entry
# ---------------------------------------------------------------------------
class TestAmendmentsToLedgerEntry:
    def test_structure(self, sample_hashes):
        entry = amendments_to_ledger_entry(sample_hashes)
        assert entry["LedgerEntryType"] == "Amendments"
        assert entry["Amendments"] == sample_hashes
        assert entry["Flags"] == 0

    def test_index_matches_fixture(self, sample_hashes):
        entry = amendments_to_ledger_entry(sample_hashes)
        assert entry["index"] == AMENDMENTS_INDEX

    def test_empty_amendments(self):
        entry = amendments_to_ledger_entry([])
        assert entry["Amendments"] == []
        assert entry["index"] == AMENDMENTS_INDEX


# ---------------------------------------------------------------------------
# account_root_entry
# ---------------------------------------------------------------------------
class TestAccountRootEntry:
    def test_basic_structure(self):
        entry = account_root_entry(ALICE_ADDRESS, 100_000_000_000)
        assert entry["Account"] == ALICE_ADDRESS
        assert entry["Balance"] == str(100_000_000_000)
        assert entry["LedgerEntryType"] == "AccountRoot"
        assert entry["Flags"] == 0
        assert entry["OwnerCount"] == 0
        assert entry["Sequence"] == 2

    def test_custom_flags(self):
        entry = account_root_entry(ALICE_ADDRESS, 100, flags=LSF_DEFAULT_RIPPLE)
        assert entry["Flags"] == LSF_DEFAULT_RIPPLE

    def test_custom_prev_txn(self):
        txn_id = "AB" * 32
        entry = account_root_entry(ALICE_ADDRESS, 100, prev_txn_id=txn_id)
        assert entry["PreviousTxnID"] == txn_id

    def test_index_matches_indices_module(self):
        entry = account_root_entry(ALICE_ADDRESS, 100)
        assert entry["index"] == account_root_index(ALICE_ADDRESS)
        assert entry["index"] == ALICE_INDEX


# ---------------------------------------------------------------------------
# assemble_ledger_json
# ---------------------------------------------------------------------------
class TestAssembleLedgerJson:
    def test_minimal_ledger(self, alice, bob):
        ledger = assemble_ledger_json(
            accounts=[alice, bob],
            amendment_hashes=["AAAA" * 16],
        )
        assert "ledger" in ledger
        assert "accountState" in ledger["ledger"]
        assert ledger["ledger"]["accepted"] is True

    def test_genesis_first(self, alice, bob):
        ledger = assemble_ledger_json(
            accounts=[alice, bob],
            amendment_hashes=[],
        )
        state = ledger["ledger"]["accountState"]
        assert state[0]["Account"] == GENESIS_ADDRESS

    def test_genesis_gets_remaining_xrp(self, alice):
        balance = 100_000_000_000
        ledger = assemble_ledger_json(
            accounts=[alice],
            amendment_hashes=[],
            default_acct_balance=balance,
        )
        state = ledger["ledger"]["accountState"]
        genesis_entry = state[0]
        expected = TOTAL_COINS_DROPS - balance
        assert int(genesis_entry["Balance"]) == expected

    def test_total_coins(self, alice, bob):
        ledger = assemble_ledger_json(
            accounts=[alice, bob],
            amendment_hashes=[],
        )
        assert ledger["ledger"]["totalCoins"] == str(TOTAL_COINS_DROPS)
        assert ledger["ledger"]["total_coins"] == str(TOTAL_COINS_DROPS)

    def test_with_trustlines(self, alice, bob):
        tl = generate_trustline_objects(alice, bob, "USD", 1_000_000_000)
        ledger = assemble_ledger_json(
            accounts=[alice, bob],
            amendment_hashes=[],
            trustline_objects=[tl],
        )
        state = ledger["ledger"]["accountState"]
        types = [e["LedgerEntryType"] for e in state]
        assert "RippleState" in types
        assert "DirectoryNode" in types

    def test_owner_count_updated(self, alice, bob):
        tl = generate_trustline_objects(alice, bob, "USD", 1_000_000_000)
        ledger = assemble_ledger_json(
            accounts=[alice, bob],
            amendment_hashes=[],
            trustline_objects=[tl],
        )
        state = ledger["ledger"]["accountState"]
        alice_entry = next(e for e in state if e.get("Account") == ALICE_ADDRESS)
        bob_entry = next(e for e in state if e.get("Account") == BOB_ADDRESS)
        assert alice_entry["OwnerCount"] == 1
        assert bob_entry["OwnerCount"] == 1

    def test_amm_issuers_get_default_ripple(self, alice, bob):
        ledger = assemble_ledger_json(
            accounts=[alice, bob],
            amendment_hashes=[],
            amm_issuers={ALICE_ADDRESS},
        )
        state = ledger["ledger"]["accountState"]
        alice_entry = next(e for e in state if e.get("Account") == ALICE_ADDRESS)
        bob_entry = next(e for e in state if e.get("Account") == BOB_ADDRESS)
        assert alice_entry["Flags"] == LSF_DEFAULT_RIPPLE
        assert bob_entry["Flags"] == 0

    def test_with_fees(self, alice):
        fees = {
            "LedgerEntryType": "FeeSettings",
            "BaseFeeDrops": 121,
            "Flags": 0,
            "ReserveBaseDrops": 2_000_000,
            "ReserveIncrementDrops": 666,
            "index": "4BC50C9B0D8515D3EAAE1E74B29A95804346C491EE1A95BF25E4AAB854A6A651",
        }
        ledger = assemble_ledger_json(
            accounts=[alice],
            amendment_hashes=[],
            fees=fees,
        )
        state = ledger["ledger"]["accountState"]
        fee_entries = [e for e in state if e.get("LedgerEntryType") == "FeeSettings"]
        assert len(fee_entries) == 1
        assert fee_entries[0]["BaseFeeDrops"] == 121

    def test_directory_node_consolidation(self, alice, bob):
        """Multiple trustlines for same account should merge into one DirectoryNode."""
        tl1 = generate_trustline_objects(alice, bob, "USD", 1_000_000_000)
        tl2 = generate_trustline_objects(alice, bob, "EUR", 1_000_000_000)
        ledger = assemble_ledger_json(
            accounts=[alice, bob],
            amendment_hashes=[],
            trustline_objects=[tl1, tl2],
        )
        state = ledger["ledger"]["accountState"]
        dir_nodes = [e for e in state if e.get("LedgerEntryType") == "DirectoryNode"]
        # Should be 2 consolidated directories (one per account), not 4
        assert len(dir_nodes) == 2
        for dn in dir_nodes:
            assert len(dn["Indexes"]) == 2  # Both trustline indices merged
