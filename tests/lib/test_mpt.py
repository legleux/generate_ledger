"""Tests for gl.develop.mpt — MPToken ledger object generation."""

import pytest

from generate_ledger.accounts import Account
from generate_ledger.develop.mpt import (
    _build_issuance_object,
    _build_mptoken_object,
    _outstanding_amount,
    generate_mpt_objects,
)
from generate_ledger.indices import mpt_id_to_hex, mpt_issuance_index, mptoken_index
from generate_ledger.ledger import LedgerConfig, MPTHolderConfig, MPTIssuanceConfig
from tests.conftest import ALICE_ADDRESS, ALICE_SEED, BOB_ADDRESS, BOB_SEED


@pytest.fixture
def alice():
    return Account(ALICE_ADDRESS, ALICE_SEED)


@pytest.fixture
def bob():
    return Account(BOB_ADDRESS, BOB_SEED)


@pytest.fixture
def two_accounts(alice, bob):
    return [alice, bob]


# ---------------------------------------------------------------------------
# _build_issuance_object
# ---------------------------------------------------------------------------
class TestBuildIssuanceObject:
    def test_required_fields_present(self):
        obj = _build_issuance_object(ALICE_ADDRESS, sequence=1)
        assert obj["LedgerEntryType"] == "MPTokenIssuance"
        assert obj["Issuer"] == ALICE_ADDRESS
        assert obj["Sequence"] == 1
        assert obj["OutstandingAmount"] == "0"
        assert "OwnerNode" in obj
        assert "PreviousTxnID" in obj
        assert "PreviousTxnLgrSeq" in obj
        assert "index" in obj

    def test_index_matches_formula(self):
        obj = _build_issuance_object(ALICE_ADDRESS, sequence=2)
        assert obj["index"] == mpt_issuance_index(2, ALICE_ADDRESS)

    def test_flags_default_zero(self):
        obj = _build_issuance_object(ALICE_ADDRESS, sequence=1)
        assert obj["Flags"] == 0

    def test_flags_custom(self):
        obj = _build_issuance_object(ALICE_ADDRESS, sequence=1, flags=64)
        assert obj["Flags"] == 64

    def test_no_optional_fields_by_default(self):
        obj = _build_issuance_object(ALICE_ADDRESS, sequence=1)
        assert "MaximumAmount" not in obj
        assert "AssetScale" not in obj
        assert "TransferFee" not in obj
        assert "MPTokenMetadata" not in obj

    def test_max_amount_present_when_set(self):
        obj = _build_issuance_object(ALICE_ADDRESS, sequence=1, max_amount="1000000")
        assert obj["MaximumAmount"] == "1000000"

    def test_asset_scale_present_when_set(self):
        obj = _build_issuance_object(ALICE_ADDRESS, sequence=1, asset_scale=2)
        assert obj["AssetScale"] == 2

    def test_transfer_fee_present_when_set(self):
        obj = _build_issuance_object(ALICE_ADDRESS, sequence=1, transfer_fee=100)
        assert obj["TransferFee"] == 100

    def test_metadata_present_when_set(self):
        obj = _build_issuance_object(ALICE_ADDRESS, sequence=1, metadata="48656C6C6F")
        assert obj["MPTokenMetadata"] == "48656C6C6F"

    def test_owner_node_hex_string(self):
        obj = _build_issuance_object(ALICE_ADDRESS, sequence=1)
        assert obj["OwnerNode"] == "0000000000000000"

    def test_prev_txn_id_zeroes(self):
        obj = _build_issuance_object(ALICE_ADDRESS, sequence=1)
        assert obj["PreviousTxnID"] == "0" * 64

    def test_different_sequences_different_index(self):
        obj1 = _build_issuance_object(ALICE_ADDRESS, sequence=1)
        obj2 = _build_issuance_object(ALICE_ADDRESS, sequence=2)
        assert obj1["index"] != obj2["index"]


# ---------------------------------------------------------------------------
# _build_mptoken_object
# ---------------------------------------------------------------------------
class TestBuildMptokenObject:
    def test_required_fields_present(self):
        issuance_idx = mpt_issuance_index(1, ALICE_ADDRESS)
        issuance_id = mpt_id_to_hex(1, ALICE_ADDRESS)
        obj = _build_mptoken_object(issuance_idx, issuance_id, BOB_ADDRESS, "500")
        assert obj["LedgerEntryType"] == "MPToken"
        assert obj["Account"] == BOB_ADDRESS
        assert obj["MPTAmount"] == "500"
        assert obj["Flags"] == 0
        assert "MPTokenIssuanceID" in obj
        assert "OwnerNode" in obj
        assert "index" in obj

    def test_index_matches_formula(self):
        issuance_idx = mpt_issuance_index(1, ALICE_ADDRESS)
        issuance_id = mpt_id_to_hex(1, ALICE_ADDRESS)
        obj = _build_mptoken_object(issuance_idx, issuance_id, BOB_ADDRESS, "500")
        assert obj["index"] == mptoken_index(issuance_idx, BOB_ADDRESS)

    def test_issuance_id_is_48_char_hex(self):
        issuance_idx = mpt_issuance_index(1, ALICE_ADDRESS)
        issuance_id = mpt_id_to_hex(1, ALICE_ADDRESS)
        obj = _build_mptoken_object(issuance_idx, issuance_id, BOB_ADDRESS, "100")
        assert len(obj["MPTokenIssuanceID"]) == 48
        assert obj["MPTokenIssuanceID"] == obj["MPTokenIssuanceID"].upper()

    def test_owner_node_hex_string(self):
        issuance_idx = mpt_issuance_index(1, ALICE_ADDRESS)
        issuance_id = mpt_id_to_hex(1, ALICE_ADDRESS)
        obj = _build_mptoken_object(issuance_idx, issuance_id, BOB_ADDRESS, "100")
        assert obj["OwnerNode"] == "0000000000000000"

    def test_different_holders_different_index(self):
        issuance_idx = mpt_issuance_index(1, ALICE_ADDRESS)
        issuance_id = mpt_id_to_hex(1, ALICE_ADDRESS)
        obj_bob = _build_mptoken_object(issuance_idx, issuance_id, BOB_ADDRESS, "100")
        obj_alice = _build_mptoken_object(issuance_idx, issuance_id, ALICE_ADDRESS, "100")
        assert obj_bob["index"] != obj_alice["index"]


# ---------------------------------------------------------------------------
# _outstanding_amount
# ---------------------------------------------------------------------------
class TestOutstandingAmount:
    def test_empty_holders(self):
        assert _outstanding_amount([]) == "0"

    def test_single_holder(self):
        holders = [MPTHolderConfig(holder="0", amount="500")]
        assert _outstanding_amount(holders) == "500"

    def test_multiple_holders_summed(self):
        holders = [
            MPTHolderConfig(holder="0", amount="300"),
            MPTHolderConfig(holder="1", amount="200"),
        ]
        assert _outstanding_amount(holders) == "500"


# ---------------------------------------------------------------------------
# generate_mpt_objects
# ---------------------------------------------------------------------------
class TestGenerateMptObjects:
    def test_empty_issuances_returns_empty(self, two_accounts):
        config = LedgerConfig(mpt_issuances=[])
        result = generate_mpt_objects(accounts=two_accounts, config=config)
        assert result == []

    def test_single_issuance_no_holders(self, two_accounts, alice):
        config = LedgerConfig(mpt_issuances=[MPTIssuanceConfig(issuer="0", sequence=1)])
        result = generate_mpt_objects(accounts=two_accounts, config=config)
        assert len(result) == 1
        obj = result[0]
        assert obj["LedgerEntryType"] == "MPTokenIssuance"
        assert obj["Issuer"] == alice.address
        assert obj["Sequence"] == 1
        assert obj["OutstandingAmount"] == "0"

    def test_issuance_index_is_correct(self, two_accounts, alice):
        config = LedgerConfig(mpt_issuances=[MPTIssuanceConfig(issuer="0", sequence=2)])
        result = generate_mpt_objects(accounts=two_accounts, config=config)
        assert result[0]["index"] == mpt_issuance_index(2, alice.address)

    def test_issuance_with_max_amount(self, two_accounts):
        config = LedgerConfig(mpt_issuances=[MPTIssuanceConfig(issuer="0", sequence=1, max_amount="9999999")])
        result = generate_mpt_objects(accounts=two_accounts, config=config)
        assert result[0]["MaximumAmount"] == "9999999"

    def test_issuance_with_all_optional_fields(self, two_accounts):
        config = LedgerConfig(
            mpt_issuances=[
                MPTIssuanceConfig(
                    issuer="0",
                    sequence=1,
                    max_amount="1000000",
                    asset_scale=2,
                    transfer_fee=100,
                    metadata="48656C6C6F",
                    flags=64,
                )
            ]
        )
        result = generate_mpt_objects(accounts=two_accounts, config=config)
        obj = result[0]
        assert obj["MaximumAmount"] == "1000000"
        assert obj["AssetScale"] == 2
        assert obj["TransferFee"] == 100
        assert obj["MPTokenMetadata"] == "48656C6C6F"
        assert obj["Flags"] == 64

    def test_single_issuance_with_one_holder(self, two_accounts, alice, bob):
        config = LedgerConfig(
            mpt_issuances=[
                MPTIssuanceConfig(
                    issuer="0",
                    sequence=1,
                    holders=[MPTHolderConfig(holder="1", amount="500")],
                )
            ]
        )
        result = generate_mpt_objects(accounts=two_accounts, config=config)
        assert len(result) == 2  # 1 issuance + 1 mptoken

        issuance = result[0]
        mptoken = result[1]

        assert issuance["LedgerEntryType"] == "MPTokenIssuance"
        assert issuance["OutstandingAmount"] == "500"

        assert mptoken["LedgerEntryType"] == "MPToken"
        assert mptoken["Account"] == bob.address
        assert mptoken["MPTAmount"] == "500"

    def test_mptoken_issuance_id_matches_issuer(self, two_accounts, alice, bob):
        config = LedgerConfig(
            mpt_issuances=[
                MPTIssuanceConfig(
                    issuer="0",
                    sequence=1,
                    holders=[MPTHolderConfig(holder="1", amount="100")],
                )
            ]
        )
        result = generate_mpt_objects(accounts=two_accounts, config=config)
        mptoken = result[1]
        expected_id = mpt_id_to_hex(1, alice.address)
        assert mptoken["MPTokenIssuanceID"] == expected_id

    def test_multiple_holders_outstanding_amount(self, two_accounts, alice, bob):
        config = LedgerConfig(
            mpt_issuances=[
                MPTIssuanceConfig(
                    issuer="0",
                    sequence=1,
                    holders=[
                        MPTHolderConfig(holder="1", amount="300"),
                        MPTHolderConfig(holder="0", amount="200"),  # alice holds her own token
                    ],
                )
            ]
        )
        result = generate_mpt_objects(accounts=two_accounts, config=config)
        assert len(result) == 3  # 1 issuance + 2 mptokens
        assert result[0]["OutstandingAmount"] == "500"

    def test_multiple_issuances(self, two_accounts, alice, bob):
        config = LedgerConfig(
            mpt_issuances=[
                MPTIssuanceConfig(issuer="0", sequence=1),
                MPTIssuanceConfig(issuer="0", sequence=2),
                MPTIssuanceConfig(issuer="1", sequence=1),
            ]
        )
        result = generate_mpt_objects(accounts=two_accounts, config=config)
        assert len(result) == 3
        indices = [obj["index"] for obj in result]
        assert len(set(indices)) == 3  # all unique

    def test_resolve_by_address(self, two_accounts, alice):
        """Issuer can be specified by classic address, not just index."""
        config = LedgerConfig(mpt_issuances=[MPTIssuanceConfig(issuer=alice.address, sequence=1)])
        result = generate_mpt_objects(accounts=two_accounts, config=config)
        assert result[0]["Issuer"] == alice.address

    def test_invalid_account_index_raises(self, two_accounts):
        config = LedgerConfig(mpt_issuances=[MPTIssuanceConfig(issuer="99", sequence=1)])
        with pytest.raises(ValueError, match="out of range"):
            generate_mpt_objects(accounts=two_accounts, config=config)

    def test_unknown_address_raises(self, two_accounts):
        config = LedgerConfig(mpt_issuances=[MPTIssuanceConfig(issuer="rUnknownXXXXXXXXXXXXXXXXXXXXXXX", sequence=1)])
        with pytest.raises(ValueError, match="not found"):
            generate_mpt_objects(accounts=two_accounts, config=config)
