"""Tests for the gateway topology trustline generation module."""

import time

import pytest

from generate_ledger.accounts import Account, AccountConfig, generate_accounts
from generate_ledger.gateways import (
    GatewayConfig,
    _build_gateway_assets,
    generate_gateway_trustlines,
    generate_trustline_objects_fast,
)
from generate_ledger.trustlines import TrustlineObjects
from tests.xrpl_validators import assert_valid_ripple_state

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_accounts(n: int) -> list[Account]:
    return generate_accounts(AccountConfig(num_accounts=n, algo="ed25519"))


# ---------------------------------------------------------------------------
# GatewayConfig defaults
# ---------------------------------------------------------------------------
class TestGatewayConfig:
    def test_defaults(self):
        cfg = GatewayConfig()
        assert cfg.num_gateways == 0
        assert cfg.assets_per_gateway == 4
        assert cfg.coverage == 0.5
        assert cfg.connectivity == 0.5
        assert len(cfg.currencies) == 16

    def test_disabled_by_default(self):
        cfg = GatewayConfig()
        accounts = _make_accounts(5)
        tls, gw_addrs = generate_gateway_trustlines(accounts, cfg)
        assert tls == []
        assert gw_addrs == set()


# ---------------------------------------------------------------------------
# _build_gateway_assets
# ---------------------------------------------------------------------------
class TestBuildGatewayAssets:
    def test_4x4(self):
        cfg = GatewayConfig(num_gateways=4, assets_per_gateway=4)
        assets = _build_gateway_assets(cfg)
        assert len(assets) == 4
        for gw_idx in range(4):
            assert len(assets[gw_idx]) == 4

    def test_round_robin_distribution(self):
        cfg = GatewayConfig(
            num_gateways=2,
            assets_per_gateway=3,
            currencies=["A", "B", "C", "D", "E", "F"],
        )
        assets = _build_gateway_assets(cfg)
        assert assets[0] == ["A", "B", "C"]
        assert assets[1] == ["D", "E", "F"]

    def test_currency_cycling(self):
        cfg = GatewayConfig(
            num_gateways=2,
            assets_per_gateway=3,
            currencies=["USD", "EUR"],
        )
        assets = _build_gateway_assets(cfg)
        # Cycles: USD, EUR, USD, EUR, USD, EUR
        assert assets[0] == ["USD", "EUR", "USD"]
        assert assets[1] == ["EUR", "USD", "EUR"]


# ---------------------------------------------------------------------------
# generate_trustline_objects_fast
# ---------------------------------------------------------------------------
class TestGenerateTrustlineObjectsFast:
    @pytest.fixture
    def accounts(self):
        return _make_accounts(2)

    def test_returns_trustline_objects(self, accounts):
        tl = generate_trustline_objects_fast(accounts[0], accounts[1], "USD", 1000)
        assert isinstance(tl, TrustlineObjects)

    def test_ripple_state_structure(self, accounts):
        tl = generate_trustline_objects_fast(accounts[0], accounts[1], "USD", 1000)
        rs = tl.ripple_state
        assert rs["LedgerEntryType"] == "RippleState"
        assert rs["Balance"]["currency"] == "USD"
        assert rs["Balance"]["value"] == "0"
        assert rs["Flags"] == 131072
        assert rs["HighLimit"]["value"] == "1000"
        assert rs["LowLimit"]["value"] == "1000"

    def test_high_low_ordering(self, accounts):
        tl = generate_trustline_objects_fast(accounts[0], accounts[1], "USD", 1000)
        assert_valid_ripple_state(tl.ripple_state)

    def test_directory_nodes_reference_rsi(self, accounts):
        tl = generate_trustline_objects_fast(accounts[0], accounts[1], "USD", 1000)
        rsi = tl.ripple_state["index"]
        assert rsi in tl.directory_node_a["Indexes"]
        assert rsi in tl.directory_node_b["Indexes"]

    def test_synthetic_txn_id_equals_rsi(self, accounts):
        tl = generate_trustline_objects_fast(accounts[0], accounts[1], "USD", 1000)
        rsi = tl.ripple_state["index"]
        assert tl.ripple_state["PreviousTxnID"] == rsi
        assert tl.directory_node_a["PreviousTxnID"] == rsi

    def test_deterministic(self, accounts):
        tl1 = generate_trustline_objects_fast(accounts[0], accounts[1], "USD", 1000)
        tl2 = generate_trustline_objects_fast(accounts[0], accounts[1], "USD", 1000)
        assert tl1.ripple_state["index"] == tl2.ripple_state["index"]

    def test_ledger_seq_propagated(self, accounts):
        tl = generate_trustline_objects_fast(accounts[0], accounts[1], "USD", 1000, ledger_seq=7)
        assert tl.ripple_state["PreviousTxnLgrSeq"] == 7
        assert tl.directory_node_a["PreviousTxnLgrSeq"] == 7


# ---------------------------------------------------------------------------
# generate_gateway_trustlines
# ---------------------------------------------------------------------------
class TestGenerateGatewayTrustlines:
    def test_disabled_returns_empty(self):
        accounts = _make_accounts(5)
        tls, addrs = generate_gateway_trustlines(accounts, GatewayConfig(num_gateways=0))
        assert tls == []
        assert addrs == set()

    def test_too_few_accounts_raises(self):
        accounts = _make_accounts(2)
        with pytest.raises(ValueError, match="Need more accounts"):
            generate_gateway_trustlines(accounts, GatewayConfig(num_gateways=3))

    def test_basic_count(self):
        """4 gateways, 2 assets each, 20 regular accounts, full coverage + connectivity."""
        accounts = _make_accounts(24)  # 4 gw + 20 regular
        cfg = GatewayConfig(
            num_gateways=4,
            assets_per_gateway=2,
            currencies=["USD", "EUR", "GBP", "JPY", "BTC", "ETH", "CNY", "MXN"],
            coverage=1.0,
            connectivity=1.0,
            seed=42,
        )
        tls, _gw_addrs = generate_gateway_trustlines(accounts, cfg)
        # 20 holders * 4 gateways * 2 assets = 160
        assert len(tls) == 160

    def test_gateway_addresses_returned(self):
        accounts = _make_accounts(10)
        cfg = GatewayConfig(
            num_gateways=2, assets_per_gateway=1, currencies=["USD", "EUR"], coverage=1.0, connectivity=1.0, seed=1
        )
        _, gw_addrs = generate_gateway_trustlines(accounts, cfg)
        assert gw_addrs == {accounts[0].address, accounts[1].address}

    def test_coverage_fraction(self):
        """With coverage=0.5, roughly half the regular accounts get trustlines."""
        accounts = _make_accounts(104)  # 4 gw + 100 regular
        cfg = GatewayConfig(
            num_gateways=4,
            assets_per_gateway=1,
            currencies=["USD", "EUR", "GBP", "JPY"],
            coverage=0.5,
            connectivity=1.0,
            seed=42,
        )
        tls, _ = generate_gateway_trustlines(accounts, cfg)
        # 50 holders * 4 gateways * 1 asset = 200
        assert len(tls) == 200

    def test_connectivity_fraction(self):
        """With connectivity=0.5, each holder connects to ~half the gateways."""
        accounts = _make_accounts(14)  # 4 gw + 10 regular
        cfg = GatewayConfig(
            num_gateways=4,
            assets_per_gateway=1,
            currencies=["USD", "EUR", "GBP", "JPY"],
            coverage=1.0,
            connectivity=0.5,
            seed=42,
        )
        tls, _ = generate_gateway_trustlines(accounts, cfg)
        # 10 holders * 2 gateways (50% of 4) * 1 asset = 20
        assert len(tls) == 20

    def test_no_duplicate_trustlines(self):
        accounts = _make_accounts(24)
        cfg = GatewayConfig(
            num_gateways=4,
            assets_per_gateway=2,
            currencies=["USD", "EUR", "GBP", "JPY", "BTC", "ETH", "CNY", "MXN"],
            coverage=1.0,
            connectivity=1.0,
            seed=99,
        )
        tls, _ = generate_gateway_trustlines(accounts, cfg)
        indices = [tl.ripple_state["index"] for tl in tls]
        assert len(indices) == len(set(indices))

    def test_reproducible_with_seed(self):
        accounts = _make_accounts(20)
        cfg = GatewayConfig(
            num_gateways=2,
            assets_per_gateway=2,
            currencies=["USD", "EUR", "GBP", "JPY"],
            coverage=0.6,
            connectivity=0.5,
            seed=123,
        )
        tls1, _ = generate_gateway_trustlines(accounts, cfg)
        tls2, _ = generate_gateway_trustlines(accounts, cfg)
        idx1 = [tl.ripple_state["index"] for tl in tls1]
        idx2 = [tl.ripple_state["index"] for tl in tls2]
        assert idx1 == idx2

    def test_different_seed_different_result(self):
        accounts = _make_accounts(20)
        cfg1 = GatewayConfig(
            num_gateways=2,
            assets_per_gateway=2,
            currencies=["USD", "EUR", "GBP", "JPY"],
            coverage=0.5,
            connectivity=0.5,
            seed=1,
        )
        cfg2 = GatewayConfig(
            num_gateways=2,
            assets_per_gateway=2,
            currencies=["USD", "EUR", "GBP", "JPY"],
            coverage=0.5,
            connectivity=0.5,
            seed=2,
        )
        tls1, _ = generate_gateway_trustlines(accounts, cfg1)
        tls2, _ = generate_gateway_trustlines(accounts, cfg2)
        idx1 = {tl.ripple_state["index"] for tl in tls1}
        idx2 = {tl.ripple_state["index"] for tl in tls2}
        assert idx1 != idx2


# ---------------------------------------------------------------------------
# Scale smoke test
# ---------------------------------------------------------------------------
class TestScaleSmoke:
    def test_1000_accounts_4_gateways(self):
        """Moderate scale: 1000 accounts, 4 gateways, 4 assets each."""
        accounts = _make_accounts(1004)
        cfg = GatewayConfig(
            num_gateways=4,
            assets_per_gateway=4,
            coverage=0.5,
            connectivity=0.5,
            seed=42,
        )
        t0 = time.monotonic()
        tls, gw_addrs = generate_gateway_trustlines(accounts, cfg)
        elapsed = time.monotonic() - t0

        # 500 holders * 2 gateways * 4 assets = 4000
        assert len(tls) == 4000
        assert len(gw_addrs) == 4
        # Should complete in well under 30 seconds
        assert elapsed < 30, f"Too slow: {elapsed:.1f}s for 4000 trustlines"

    def test_gateway_accounts_are_first_n(self):
        accounts = _make_accounts(10)
        cfg = GatewayConfig(
            num_gateways=3,
            assets_per_gateway=1,
            currencies=["USD", "EUR", "GBP"],
            coverage=1.0,
            connectivity=1.0,
            seed=1,
        )
        _, gw_addrs = generate_gateway_trustlines(accounts, cfg)
        expected = {accounts[i].address for i in range(3)}
        assert gw_addrs == expected
