"""Integration tests for gen_ledger_state — full pipeline through ledger generation."""
import pytest
from gl.accounts import Account, AccountConfig
from gl.amendments import amendment_hash, get_amendments_for_profile
from gl.ledger import (
    AMMPoolConfig,
    ExplicitTrustline,
    FeeConfig,
    LedgerConfig,
    _resolve_account_ref,
    _resolve_account_to_object,
    gen_ledger_state,
)
from gl.trustlines import TrustlineConfig
from tests.conftest import ALICE_ADDRESS, ALICE_SEED, AMENDMENTS_INDEX, BOB_ADDRESS, BOB_SEED


@pytest.fixture
def alice():
    return Account(ALICE_ADDRESS, ALICE_SEED)


@pytest.fixture
def bob():
    return Account(BOB_ADDRESS, BOB_SEED)


# ---------------------------------------------------------------------------
# _resolve_account_ref
# ---------------------------------------------------------------------------
class TestResolveAccountRef:
    def test_by_index(self, alice, bob):
        result = _resolve_account_ref("0", [alice, bob])
        assert result == ALICE_ADDRESS

    def test_by_address(self, alice, bob):
        result = _resolve_account_ref(BOB_ADDRESS, [alice, bob])
        assert result == BOB_ADDRESS

    def test_none(self, alice):
        result = _resolve_account_ref(None, [alice])
        assert result is None

    def test_out_of_range(self, alice):
        with pytest.raises(ValueError, match="out of range"):
            _resolve_account_ref("5", [alice])


# ---------------------------------------------------------------------------
# _resolve_account_to_object
# ---------------------------------------------------------------------------
class TestResolveAccountToObject:
    def test_by_index(self, alice, bob):
        result = _resolve_account_to_object("0", [alice, bob])
        assert result is alice

    def test_by_address(self, alice, bob):
        result = _resolve_account_to_object(BOB_ADDRESS, [alice, bob])
        assert result is bob

    def test_not_found_raises(self, alice):
        with pytest.raises(ValueError, match="not found"):
            _resolve_account_to_object("rNotAnAddress", [alice])


# ---------------------------------------------------------------------------
# FeeConfig
# ---------------------------------------------------------------------------
class TestFeeConfig:
    def test_xrpl_format(self):
        fc = FeeConfig()
        result = fc.xrpl
        assert result["LedgerEntryType"] == "FeeSettings"
        assert result["BaseFeeDrops"] == 121
        assert result["ReserveBaseDrops"] == 2_000_000
        assert result["ReserveIncrementDrops"] == 666
        assert result["Flags"] == 0
        assert result["index"] == "4BC50C9B0D8515D3EAAE1E74B29A95804346C491EE1A95BF25E4AAB854A6A651"

    def test_custom_fees(self):
        fc = FeeConfig(base_fee_drops=10, reserve_base_drops=1_000_000, reserve_increment_drops=500)
        assert fc.xrpl["BaseFeeDrops"] == 10


# ---------------------------------------------------------------------------
# gen_ledger_state (full pipeline)
# ---------------------------------------------------------------------------
class TestGenLedgerState:
    def test_basic_accounts_only(self, tmp_path):
        cfg = LedgerConfig(
            account_cfg=AccountConfig(num_accounts=2),
            base_dir=tmp_path,
        )
        ledger = gen_ledger_state(cfg)
        assert "ledger" in ledger
        state = ledger["ledger"]["accountState"]
        # genesis + 2 accounts + fees + amendments = 5
        account_roots = [e for e in state if e.get("LedgerEntryType") == "AccountRoot"]
        assert len(account_roots) == 3  # genesis + 2

    def test_with_random_trustlines(self, tmp_path):
        cfg = LedgerConfig(
            account_cfg=AccountConfig(num_accounts=3),
            trustlines=TrustlineConfig(num_trustlines=2, currencies=["USD"]),
            base_dir=tmp_path,
        )
        ledger = gen_ledger_state(cfg)
        state = ledger["ledger"]["accountState"]
        types = [e.get("LedgerEntryType") for e in state]
        assert "RippleState" in types

    def test_with_explicit_trustlines(self, tmp_path):
        cfg = LedgerConfig(
            account_cfg=AccountConfig(num_accounts=2),
            explicit_trustlines=[
                ExplicitTrustline(account1="0", account2="1", currency="USD", limit=1_000_000_000),
            ],
            base_dir=tmp_path,
        )
        ledger = gen_ledger_state(cfg)
        state = ledger["ledger"]["accountState"]
        rs_entries = [e for e in state if e.get("LedgerEntryType") == "RippleState"]
        assert len(rs_entries) == 1

    def test_with_amm_pool(self, tmp_path):
        cfg = LedgerConfig(
            account_cfg=AccountConfig(num_accounts=2),
            explicit_trustlines=[
                ExplicitTrustline(account1="0", account2="1", currency="USD", limit=1_000_000_000),
            ],
            amm_pools=[
                AMMPoolConfig(
                    asset1_currency=None,
                    asset1_issuer=None,
                    asset1_amount="1000000000000",
                    asset2_currency="USD",
                    asset2_issuer="0",
                    asset2_amount="1000000",
                    trading_fee=500,
                    creator="0",
                ),
            ],
            base_dir=tmp_path,
        )
        ledger = gen_ledger_state(cfg)
        state = ledger["ledger"]["accountState"]
        types = [e.get("LedgerEntryType") for e in state]
        assert "AMM" in types


# ---------------------------------------------------------------------------
# Amendments in ledger output
# ---------------------------------------------------------------------------

def _get_amendments_entry(ledger: dict) -> dict:
    """Extract the single Amendments entry from generated ledger output."""
    entries = [
        e for e in ledger["ledger"]["accountState"]
        if e.get("LedgerEntryType") == "Amendments"
    ]
    assert len(entries) == 1, f"Expected 1 Amendments entry, found {len(entries)}"
    return entries[0]


class TestAmendmentsInLedger:
    """Verify that amendments flow through gen_ledger_state() into the ledger output."""

    def test_amendments_entry_present(self, tmp_path):
        """Amendments entry exists with correct index and non-empty hash list."""
        cfg = LedgerConfig(
            account_cfg=AccountConfig(num_accounts=2),
            amendment_profile="release",
            base_dir=tmp_path,
        )
        ledger = gen_ledger_state(cfg)
        entry = _get_amendments_entry(ledger)

        assert entry["index"] == AMENDMENTS_INDEX
        assert entry["Flags"] == 0
        assert isinstance(entry["Amendments"], list)
        assert len(entry["Amendments"]) > 0

    def test_release_profile_hashes(self, tmp_path):
        """Release profile produces the exact set of enabled hashes from amendments_release.json."""
        cfg = LedgerConfig(
            account_cfg=AccountConfig(num_accounts=2),
            amendment_profile="release",
            base_dir=tmp_path,
        )
        ledger = gen_ledger_state(cfg)
        entry = _get_amendments_entry(ledger)
        output_hashes = set(entry["Amendments"])

        # Independently load expected hashes
        amendments = get_amendments_for_profile(profile="release")
        expected_hashes = {a.index for a in amendments if a.enabled}

        assert output_hashes == expected_hashes

    def test_known_amendments_present(self, tmp_path):
        """Spot-check that well-known amendment hashes appear in the output."""
        cfg = LedgerConfig(
            account_cfg=AccountConfig(num_accounts=2),
            amendment_profile="release",
            base_dir=tmp_path,
        )
        ledger = gen_ledger_state(cfg)
        output_hashes = set(_get_amendments_entry(ledger)["Amendments"])

        for name in ("AMM", "XRPFees", "DID", "Clawback"):
            h = amendment_hash(name)
            assert h in output_hashes, f"{name} ({h}) missing from output"

    def test_obsolete_amendments_excluded(self, tmp_path):
        """Obsolete amendments (enabled=false in release JSON) must not appear in output."""
        cfg = LedgerConfig(
            account_cfg=AccountConfig(num_accounts=2),
            amendment_profile="release",
            base_dir=tmp_path,
        )
        ledger = gen_ledger_state(cfg)
        output_hashes = set(_get_amendments_entry(ledger)["Amendments"])

        obsolete_names = [
            "fixNFTokenNegOffer",
            "fixNFTokenDirV1",
            "NonFungibleTokensV1",
            "CryptoConditionsSuite",
        ]
        for name in obsolete_names:
            h = amendment_hash(name)
            assert h not in output_hashes, f"Obsolete amendment {name} ({h}) should not be in output"

    def test_disable_override_removes_amendment(self, tmp_path):
        """--disable-amendment AMM removes AMM hash from the output."""
        cfg = LedgerConfig(
            account_cfg=AccountConfig(num_accounts=2),
            amendment_profile="release",
            disable_amendments=["AMM"],
            base_dir=tmp_path,
        )
        ledger = gen_ledger_state(cfg)
        output_hashes = set(_get_amendments_entry(ledger)["Amendments"])

        assert amendment_hash("AMM") not in output_hashes

    def test_enable_override_adds_amendment(self, tmp_path):
        """--enable-amendment forces an obsolete amendment into the output."""
        cfg = LedgerConfig(
            account_cfg=AccountConfig(num_accounts=2),
            amendment_profile="release",
            enable_amendments=["fixNFTokenNegOffer"],
            base_dir=tmp_path,
        )
        ledger = gen_ledger_state(cfg)
        output_hashes = set(_get_amendments_entry(ledger)["Amendments"])

        assert amendment_hash("fixNFTokenNegOffer") in output_hashes
