"""Tests for gl.amm — AMM (Automated Market Maker) ledger object generation.

This is the largest untested module (472 lines) with two critical bug fixes.
"""

import math

import pytest

from generate_ledger.amm import (
    AMM_ACCOUNT_FLAGS,
    LSF_AMM_NODE,
    LSF_DEFAULT_RIPPLE,
    LSF_DEPOSIT_AUTH,
    LSF_DISABLE_MASTER,
    AMMObjects,
    AMMSpec,
    Asset,
    calculate_lp_tokens,
    generate_amm_objects,
    generate_amms,
)
from tests.conftest import ALICE_ADDRESS


@pytest.fixture
def xrp_asset():
    return Asset(currency=None, issuer=None, amount="1000000000000")  # 1M XRP in drops


@pytest.fixture
def usd_asset(alice):
    return Asset(currency="USD", issuer=alice.address, amount="1000000")


@pytest.fixture
def xrp_usd_spec(xrp_asset, usd_asset, alice):
    return AMMSpec(asset1=xrp_asset, asset2=usd_asset, trading_fee=500, creator=alice)


# ---------------------------------------------------------------------------
# Asset
# ---------------------------------------------------------------------------
class TestAsset:
    def test_xrp_asset(self, xrp_asset):
        assert xrp_asset.is_xrp()
        assert xrp_asset.currency is None
        assert xrp_asset.issuer is None

    def test_issued_asset(self, usd_asset):
        assert not usd_asset.is_xrp()
        assert usd_asset.currency == "USD"
        assert usd_asset.issuer == ALICE_ADDRESS

    def test_to_amount_dict_xrp(self, xrp_asset):
        result = xrp_asset.to_amount_dict()
        assert result == "1000000000000"  # XRP is just a string

    def test_to_amount_dict_issued(self, usd_asset):
        result = usd_asset.to_amount_dict()
        assert result == {
            "currency": "USD",
            "issuer": ALICE_ADDRESS,
            "value": "1000000",
        }

    def test_to_issue_dict_xrp(self, xrp_asset):
        result = xrp_asset.to_issue_dict()
        assert result == {"currency": "XRP"}

    def test_to_issue_dict_issued(self, usd_asset):
        result = usd_asset.to_issue_dict()
        assert result == {"currency": "USD", "issuer": ALICE_ADDRESS}


# ---------------------------------------------------------------------------
# calculate_lp_tokens
# ---------------------------------------------------------------------------
class TestCalculateLpTokens:
    def test_geometric_mean(self, xrp_asset, usd_asset):
        result = calculate_lp_tokens(xrp_asset, usd_asset)
        expected = math.sqrt(1_000_000_000_000 * 1_000_000)
        assert float(result) == pytest.approx(expected)

    def test_asymmetric(self):
        a = Asset(currency=None, issuer=None, amount="100")
        b = Asset(currency=None, issuer=None, amount="400")
        result = float(calculate_lp_tokens(a, b))
        assert result == pytest.approx(200.0)

    def test_large_amounts(self):
        a = Asset(currency=None, issuer=None, amount="1000000000000000")
        b = Asset(currency=None, issuer=None, amount="1000000000000000")
        result = calculate_lp_tokens(a, b)
        assert float(result) > 0


# ---------------------------------------------------------------------------
# AMM flags — critical bug fix regression tests
# ---------------------------------------------------------------------------
class TestAMMFlags:
    def test_lsf_amm_node_value(self):
        """lsfAMMNode MUST be 0x01000000, NOT 0x02000000 (lsfLowDeepFreeze)."""
        assert LSF_AMM_NODE == 0x01000000

    def test_lsf_amm_node_not_deep_freeze(self):
        """0x02000000 is lsfLowDeepFreeze which would freeze the trustline."""
        assert LSF_AMM_NODE != 0x02000000

    def test_amm_account_flags(self):
        expected = LSF_DISABLE_MASTER | LSF_DEFAULT_RIPPLE | LSF_DEPOSIT_AUTH
        assert AMM_ACCOUNT_FLAGS == expected
        assert AMM_ACCOUNT_FLAGS == 0x01900000


# ---------------------------------------------------------------------------
# generate_amm_objects
# ---------------------------------------------------------------------------
class TestGenerateAmmObjects:
    def test_returns_amm_objects(self, xrp_usd_spec):
        result = generate_amm_objects(xrp_usd_spec)
        assert isinstance(result, AMMObjects)

    def test_amm_structure(self, xrp_usd_spec):
        result = generate_amm_objects(xrp_usd_spec)
        amm = result.amm
        assert amm["LedgerEntryType"] == "AMM"
        assert amm["TradingFee"] == 500
        assert amm["Flags"] == 0
        assert len(amm["index"]) == 64

    def test_amm_account_structure(self, xrp_usd_spec):
        result = generate_amm_objects(xrp_usd_spec)
        acct = result.amm_account
        assert acct["LedgerEntryType"] == "AccountRoot"
        assert acct["Flags"] == AMM_ACCOUNT_FLAGS
        assert acct["Sequence"] == 0  # Pseudo-accounts
        assert "AMMID" in acct
        assert acct["AMMID"] == result.amm["index"]

    def test_amm_account_holds_xrp(self, xrp_usd_spec):
        """For XRP/token pools, AMM account holds the deposited XRP."""
        result = generate_amm_objects(xrp_usd_spec)
        assert result.amm_account["Balance"] == "1000000000000"

    def test_amm_account_owner_count(self, xrp_usd_spec):
        result = generate_amm_objects(xrp_usd_spec)
        assert result.amm_account["OwnerCount"] == 1

    def test_directory_contains_amm_index(self, xrp_usd_spec):
        result = generate_amm_objects(xrp_usd_spec)
        assert result.amm["index"] in result.directory_node["Indexes"]

    def test_lp_token_trustline(self, xrp_usd_spec):
        result = generate_amm_objects(xrp_usd_spec)
        assert result.lp_token_trustline is not None
        lp_tl = result.lp_token_trustline
        assert lp_tl["LedgerEntryType"] == "RippleState"
        assert lp_tl["Flags"] == LSF_AMM_NODE
        assert lp_tl["HighLimit"]["value"] == "0"
        assert lp_tl["LowLimit"]["value"] == "0"

    def test_asset_trustlines_with_lsf_amm_node(self, xrp_usd_spec):
        """Asset trustlines MUST have lsfAMMNode (0x01000000), NOT frozen."""
        result = generate_amm_objects(xrp_usd_spec)
        assert result.asset_trustlines is not None
        for tl in result.asset_trustlines:
            assert tl["Flags"] == LSF_AMM_NODE
            assert tl["LedgerEntryType"] == "RippleState"

    def test_xrp_usd_has_one_asset_trustline(self, xrp_usd_spec):
        """XRP/USD pool: only USD needs a trustline (XRP is held as Balance)."""
        result = generate_amm_objects(xrp_usd_spec)
        assert len(result.asset_trustlines) == 1
        assert result.asset_trustlines[0]["Balance"]["currency"] == "USD"

    def test_auction_slot(self, xrp_usd_spec):
        result = generate_amm_objects(xrp_usd_spec)
        amm = result.amm
        assert "AuctionSlot" in amm
        slot = amm["AuctionSlot"]
        assert slot["Account"] == ALICE_ADDRESS
        assert slot["Expiration"] > 0

    def test_vote_slots(self, xrp_usd_spec):
        result = generate_amm_objects(xrp_usd_spec)
        amm = result.amm
        assert "VoteSlots" in amm
        assert len(amm["VoteSlots"]) == 1
        vote = amm["VoteSlots"][0]["VoteEntry"]
        assert vote["Account"] == ALICE_ADDRESS
        assert vote["TradingFee"] == 500
        assert vote["VoteWeight"] == 100000

    def test_issuer_directories(self, xrp_usd_spec):
        result = generate_amm_objects(xrp_usd_spec)
        assert result.issuer_directories is not None
        assert len(result.issuer_directories) == 1
        issuer_dn = result.issuer_directories[0]
        assert issuer_dn["Owner"] == ALICE_ADDRESS  # USD issuer

    def test_creator_lp_directory(self, xrp_usd_spec):
        result = generate_amm_objects(xrp_usd_spec)
        assert result.creator_lp_directory is not None
        assert result.creator_lp_directory["Owner"] == ALICE_ADDRESS

    def test_issued_issued_pool(self, alice, bob):
        """USD/EUR pool: 2 asset trustlines (no XRP held as Balance)."""
        usd = Asset(currency="USD", issuer=alice.address, amount="1000000")
        eur = Asset(currency="EUR", issuer=bob.address, amount="500000")
        spec = AMMSpec(asset1=usd, asset2=eur, trading_fee=500, creator=alice)
        result = generate_amm_objects(spec)
        assert result.asset_trustlines is not None
        assert len(result.asset_trustlines) == 2
        assert result.amm_account["Balance"] == "0"

    def test_no_creator(self, alice):
        """Pool without creator should have no auction/vote slots or LP trustline."""
        xrp = Asset(currency=None, issuer=None, amount="1000000")
        usd = Asset(currency="USD", issuer=alice.address, amount="1000")
        spec = AMMSpec(asset1=xrp, asset2=usd, trading_fee=500, creator=None)
        result = generate_amm_objects(spec)
        assert result.lp_token_trustline is None
        assert result.creator_lp_directory is None
        assert "AuctionSlot" not in result.amm
        assert "VoteSlots" not in result.amm

    def test_amm_account_address_is_valid(self, xrp_usd_spec):
        result = generate_amm_objects(xrp_usd_spec)
        addr = result.amm_account["Account"]
        assert addr.startswith("r")
        # AMM and account address should match
        assert result.amm["Account"] == addr

    def test_lp_token_currency_starts_03(self, xrp_usd_spec):
        result = generate_amm_objects(xrp_usd_spec)
        lp_currency = result.amm["LPTokenBalance"]["currency"]
        assert lp_currency.startswith("03")

    def test_directory_node_owner_is_amm_account(self, xrp_usd_spec):
        result = generate_amm_objects(xrp_usd_spec)
        assert result.directory_node["Owner"] == result.amm_account["Account"]


# ---------------------------------------------------------------------------
# generate_amms
# ---------------------------------------------------------------------------
class TestGenerateAmms:
    def test_empty_specs(self):
        result = generate_amms([])
        assert result == []

    def test_multiple_specs(self, alice, bob):
        xrp = Asset(currency=None, issuer=None, amount="1000000")
        usd = Asset(currency="USD", issuer=alice.address, amount="1000")
        eur = Asset(currency="EUR", issuer=bob.address, amount="500")
        specs = [
            AMMSpec(asset1=xrp, asset2=usd, trading_fee=500, creator=alice),
            AMMSpec(asset1=xrp, asset2=eur, trading_fee=300, creator=bob),
        ]
        result = generate_amms(specs)
        assert len(result) == 2
        assert all(isinstance(r, AMMObjects) for r in result)
