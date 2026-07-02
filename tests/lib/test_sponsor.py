"""Tests for Sponsor amendment Sponsorship ledger object generation."""

import pytest

from generate_ledger.accounts import Account
from generate_ledger.indices import sponsorship_index
from generate_ledger.ledger import LedgerConfig, SponsorshipConfig
from generate_ledger.sponsor import (
    LSF_SPONSORSHIP_REQUIRE_SIGN_FOR_FEE,
    LSF_SPONSORSHIP_REQUIRE_SIGN_FOR_RESERVE,
    _build_sponsorship_object,
    generate_sponsorship_objects,
)
from tests.conftest import ALICE_ADDRESS, ALICE_SEED, BOB_ADDRESS, BOB_SEED

ALICE_BOB_SPONSORSHIP_INDEX = "80DA74A29C32104053C6CF22114CD2CABC90A78896E8CA7AB08FA5C3E5FB936E"


@pytest.fixture
def alice():
    return Account(ALICE_ADDRESS, ALICE_SEED)


@pytest.fixture
def bob():
    return Account(BOB_ADDRESS, BOB_SEED)


@pytest.fixture
def two_accounts(alice, bob):
    return [alice, bob]


def test_sponsorship_index_matches_known_value():
    assert sponsorship_index(ALICE_ADDRESS, BOB_ADDRESS) == ALICE_BOB_SPONSORSHIP_INDEX


class TestBuildSponsorshipObject:
    def test_required_fields_present(self):
        obj = _build_sponsorship_object(owner=ALICE_ADDRESS, sponsee=BOB_ADDRESS)
        assert obj["LedgerEntryType"] == "Sponsorship"
        assert obj["Owner"] == ALICE_ADDRESS
        assert obj["Sponsee"] == BOB_ADDRESS
        assert obj["Flags"] == 0
        assert obj["OwnerNode"] == "0000000000000000"
        assert obj["SponseeNode"] == "0000000000000000"
        assert obj["PreviousTxnID"] == "0" * 64
        assert obj["PreviousTxnLgrSeq"] == 0
        assert obj["index"] == ALICE_BOB_SPONSORSHIP_INDEX

    def test_optional_fields_present_when_nonzero(self):
        flags = LSF_SPONSORSHIP_REQUIRE_SIGN_FOR_FEE | LSF_SPONSORSHIP_REQUIRE_SIGN_FOR_RESERVE
        obj = _build_sponsorship_object(
            owner=ALICE_ADDRESS,
            sponsee=BOB_ADDRESS,
            fee_amount="1000000",
            max_fee="10",
            reserve_count=5,
            flags=flags,
        )
        assert obj["FeeAmount"] == "1000000"
        assert obj["MaxFee"] == "10"
        assert obj["ReserveCount"] == 5
        assert obj["Flags"] == flags

    def test_zero_optional_fields_are_absent(self):
        obj = _build_sponsorship_object(
            owner=ALICE_ADDRESS,
            sponsee=BOB_ADDRESS,
            fee_amount="0",
            max_fee="0",
            reserve_count=0,
        )
        assert "FeeAmount" not in obj
        assert "MaxFee" not in obj
        assert "ReserveCount" not in obj

    def test_owner_and_sponsee_must_differ(self):
        with pytest.raises(ValueError, match="different"):
            _build_sponsorship_object(owner=ALICE_ADDRESS, sponsee=ALICE_ADDRESS)

    def test_rejects_unknown_flags(self):
        with pytest.raises(ValueError, match="Unsupported"):
            _build_sponsorship_object(owner=ALICE_ADDRESS, sponsee=BOB_ADDRESS, flags=0x00040000)


class TestGenerateSponsorshipObjects:
    def test_empty_config_returns_empty(self, two_accounts):
        config = LedgerConfig(sponsorships=[])
        assert generate_sponsorship_objects(accounts=two_accounts, config=config) == []

    def test_resolves_account_indices(self, two_accounts):
        config = LedgerConfig(
            sponsorships=[
                SponsorshipConfig(
                    owner="0",
                    sponsee="1",
                    fee_amount="1000",
                    reserve_count=2,
                )
            ]
        )
        result = generate_sponsorship_objects(accounts=two_accounts, config=config)
        assert len(result) == 1
        obj = result[0]
        assert obj["Owner"] == ALICE_ADDRESS
        assert obj["Sponsee"] == BOB_ADDRESS
        assert obj["FeeAmount"] == "1000"
        assert obj["ReserveCount"] == 2
