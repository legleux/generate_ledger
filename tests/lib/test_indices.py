"""Tests for gl.indices — cryptographic index calculations.

Every other module depends on correct indices, so these are highest priority.
Test vectors come from a running rippled node (tests/data/ledger/testnet/volumes/ledger.json).
"""
import hashlib
import re

import pytest
from xrpl.core.addresscodec import decode_classic_address

from gl.crypto import ripesha, sha512_half
from gl.indices import (
    _currency_to_160,
    _decode_account,
    _order_low_high,
    account_root_index,
    amm_account_id,
    amm_index,
    amm_lpt_currency,
    currency_code_to_bytes,
    currency_code_to_hex,
    owner_dir,
    ripple_state_index,
)
from tests.conftest import (
    ALICE_ADDRESS,
    ALICE_INDEX,
    BOB_ADDRESS,
    BOB_INDEX,
    GENESIS_ADDRESS,
    GENESIS_INDEX,
)


# ---------------------------------------------------------------------------
# sha512_half
# ---------------------------------------------------------------------------
class TestSha512Half:
    def test_empty_input(self):
        result = sha512_half(b"")
        assert len(result) == 32
        full = hashlib.sha512(b"").digest()
        assert result == full[:32]

    def test_known_vector(self):
        data = b"abc"
        result = sha512_half(data)
        assert len(result) == 32
        assert result == hashlib.sha512(data).digest()[:32]

    def test_returns_bytes(self):
        assert isinstance(sha512_half(b"test"), bytes)


# ---------------------------------------------------------------------------
# ripesha
# ---------------------------------------------------------------------------
class TestRipesha:
    def test_returns_20_bytes(self):
        result = ripesha(b"test")
        assert len(result) == 20

    def test_known_vector_vs_independent(self):
        data = b"hello"
        sha256 = hashlib.sha256(data).digest()
        ripemd = hashlib.new("ripemd160", sha256).digest()
        assert ripesha(data) == ripemd

    def test_different_input_different_output(self):
        assert ripesha(b"a") != ripesha(b"b")


# ---------------------------------------------------------------------------
# _decode_account
# ---------------------------------------------------------------------------
class TestDecodeAccount:
    def test_genesis_address_decode(self):
        result = _decode_account(GENESIS_ADDRESS)
        assert len(result) == 20
        assert isinstance(result, bytes)

    def test_roundtrip_consistency(self):
        """decode_account and xrpl-py decode_classic_address should agree."""
        our = _decode_account(ALICE_ADDRESS)
        xrpl = decode_classic_address(ALICE_ADDRESS)
        assert our == xrpl

    def test_invalid_raises(self):
        with pytest.raises(Exception):
            _decode_account("not-a-valid-address")


# ---------------------------------------------------------------------------
# _currency_to_160
# ---------------------------------------------------------------------------
class TestCurrencyConversion:
    def test_usd_to_160bit(self):
        result = _currency_to_160("USD")
        assert len(result) == 20
        # USD is placed at bytes 12..14
        assert result[12:15] == b"USD"
        # Other bytes are zero
        assert result[:12] == bytes(12)
        assert result[15:] == bytes(5)

    def test_hex_passthrough(self):
        hex_str = "00" * 20
        result = _currency_to_160(hex_str)
        assert result == bytes(20)

    def test_hex_40_chars(self):
        hex_str = "AB" * 20
        result = _currency_to_160(hex_str)
        assert result == bytes.fromhex(hex_str)

    def test_invalid_length_raises(self):
        with pytest.raises(ValueError):
            _currency_to_160("TOOLONG")

    def test_currency_code_to_bytes(self):
        result = currency_code_to_bytes("USD")
        assert len(result) == 20
        assert result[:3] == b"USD"
        assert result[3:] == bytes(17)

    def test_currency_code_to_hex(self):
        result = currency_code_to_hex("USD")
        assert len(result) == 40  # 20 bytes = 40 hex chars
        assert result[:6] == "555344"  # "USD" in hex

    def test_currency_code_too_long(self):
        with pytest.raises(ValueError, match="too long"):
            currency_code_to_bytes("A" * 21)


# ---------------------------------------------------------------------------
# account_root_index — verified against running rippled
# ---------------------------------------------------------------------------
class TestAccountRootIndex:
    def test_genesis_index(self):
        assert account_root_index(GENESIS_ADDRESS) == GENESIS_INDEX

    def test_alice_index(self):
        assert account_root_index(ALICE_ADDRESS) == ALICE_INDEX

    def test_bob_index(self):
        assert account_root_index(BOB_ADDRESS) == BOB_INDEX

    def test_returns_64_hex(self):
        result = account_root_index(GENESIS_ADDRESS)
        assert len(result) == 64
        assert all(c in "0123456789ABCDEF" for c in result)

    def test_different_accounts_different_indices(self):
        assert account_root_index(ALICE_ADDRESS) != account_root_index(BOB_ADDRESS)


# ---------------------------------------------------------------------------
# _order_low_high
# ---------------------------------------------------------------------------
class TestOrderLowHigh:
    def test_ordering(self):
        a = bytes(range(20))
        b = bytes(range(1, 21))
        low, high = _order_low_high(a, b)
        assert low <= high

    def test_commutative(self):
        a = bytes(range(20))
        b = bytes(range(1, 21))
        assert _order_low_high(a, b) == _order_low_high(b, a)

    def test_invalid_length_raises(self):
        with pytest.raises(ValueError):
            _order_low_high(bytes(10), bytes(20))


# ---------------------------------------------------------------------------
# ripple_state_index
# ---------------------------------------------------------------------------
class TestRippleStateIndex:
    def test_known_pair(self):
        result = ripple_state_index(ALICE_ADDRESS, BOB_ADDRESS, "USD")
        assert len(result) == 64
        assert all(c in "0123456789ABCDEF" for c in result)

    def test_commutativity(self):
        """RippleState index is the same regardless of account order."""
        idx1 = ripple_state_index(ALICE_ADDRESS, BOB_ADDRESS, "USD")
        idx2 = ripple_state_index(BOB_ADDRESS, ALICE_ADDRESS, "USD")
        assert idx1 == idx2

    def test_different_currencies_differ(self):
        idx_usd = ripple_state_index(ALICE_ADDRESS, BOB_ADDRESS, "USD")
        idx_eur = ripple_state_index(ALICE_ADDRESS, BOB_ADDRESS, "EUR")
        assert idx_usd != idx_eur

    def test_different_accounts_differ(self):
        idx1 = ripple_state_index(ALICE_ADDRESS, BOB_ADDRESS, "USD")
        idx2 = ripple_state_index(ALICE_ADDRESS, GENESIS_ADDRESS, "USD")
        assert idx1 != idx2


# ---------------------------------------------------------------------------
# owner_dir
# ---------------------------------------------------------------------------
class TestOwnerDir:
    def test_deterministic(self):
        assert owner_dir(ALICE_ADDRESS) == owner_dir(ALICE_ADDRESS)

    def test_different_accounts_differ(self):
        assert owner_dir(ALICE_ADDRESS) != owner_dir(BOB_ADDRESS)

    def test_returns_64_hex(self):
        result = owner_dir(ALICE_ADDRESS)
        assert len(result) == 64
        assert all(c in "0123456789ABCDEF" for c in result)


# ---------------------------------------------------------------------------
# amm_index
# ---------------------------------------------------------------------------
class TestAmmIndex:
    def test_xrp_usd(self):
        """XRP/USD pool: XRP has None/None, USD has issuer/currency."""
        result = amm_index(None, None, ALICE_ADDRESS, "USD")
        assert len(result) == 64

    def test_commutativity(self):
        """Asset order should not matter (internal sorting)."""
        idx1 = amm_index(None, None, ALICE_ADDRESS, "USD")
        idx2 = amm_index(ALICE_ADDRESS, "USD", None, None)
        assert idx1 == idx2

    def test_issued_issued_pair(self):
        idx = amm_index(ALICE_ADDRESS, "USD", BOB_ADDRESS, "EUR")
        assert len(idx) == 64

    def test_different_pairs_differ(self):
        idx1 = amm_index(None, None, ALICE_ADDRESS, "USD")
        idx2 = amm_index(None, None, ALICE_ADDRESS, "EUR")
        assert idx1 != idx2


# ---------------------------------------------------------------------------
# amm_account_id
# ---------------------------------------------------------------------------
class TestAmmAccountId:
    def test_returns_valid_r_address(self):
        idx = amm_index(None, None, ALICE_ADDRESS, "USD")
        address = amm_account_id(idx)
        assert address.startswith("r")
        # Valid xrpl address can be decoded
        decoded = decode_classic_address(address)
        assert len(decoded) == 20

    def test_deterministic(self):
        idx = amm_index(None, None, ALICE_ADDRESS, "USD")
        assert amm_account_id(idx) == amm_account_id(idx)

    def test_default_parent_hash_is_zeros(self):
        idx = amm_index(None, None, ALICE_ADDRESS, "USD")
        addr1 = amm_account_id(idx)
        addr2 = amm_account_id(idx, parent_hash=bytes(32))
        assert addr1 == addr2

    def test_different_parent_hash_changes_address(self):
        idx = amm_index(None, None, ALICE_ADDRESS, "USD")
        addr1 = amm_account_id(idx, parent_hash=bytes(32))
        addr2 = amm_account_id(idx, parent_hash=b"\x01" * 32)
        assert addr1 != addr2

    def test_different_amm_index_different_account(self):
        idx1 = amm_index(None, None, ALICE_ADDRESS, "USD")
        idx2 = amm_index(None, None, ALICE_ADDRESS, "EUR")
        assert amm_account_id(idx1) != amm_account_id(idx2)


# ---------------------------------------------------------------------------
# amm_lpt_currency
# ---------------------------------------------------------------------------
class TestAmmLptCurrency:
    def test_starts_with_03(self):
        result = amm_lpt_currency(None, "USD")
        assert result.startswith("03")

    def test_returns_40_hex(self):
        result = amm_lpt_currency(None, "USD")
        assert len(result) == 40
        assert all(c in "0123456789ABCDEF" for c in result)

    def test_commutativity(self):
        lpt1 = amm_lpt_currency(None, "USD")
        lpt2 = amm_lpt_currency("USD", None)
        assert lpt1 == lpt2

    def test_different_pairs_differ(self):
        lpt1 = amm_lpt_currency(None, "USD")
        lpt2 = amm_lpt_currency(None, "EUR")
        assert lpt1 != lpt2

    def test_issued_issued(self):
        lpt = amm_lpt_currency("USD", "EUR")
        assert lpt.startswith("03")
        assert len(lpt) == 40
