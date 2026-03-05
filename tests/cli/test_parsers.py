"""Tests for CLI parsers."""
import pytest

from gl.cli.parsers import (
    ParseError,
    parse_amm_pool,
    parse_mpt_spec,
    parse_trustline,
)


class TestParseTrustline:
    """Tests for parse_trustline function."""

    def test_valid_with_indices(self):
        result = parse_trustline("0:1:USD:1000000000")
        assert result.account1 == "0"
        assert result.account2 == "1"
        assert result.currency == "USD"
        assert result.limit == 1000000000

    def test_valid_with_addresses(self):
        result = parse_trustline("rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh:rPT1Sjq2YGrBMTttX4GZHjKu9dyfzbpAYe:EUR:500000")
        assert result.account1 == "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh"
        assert result.account2 == "rPT1Sjq2YGrBMTttX4GZHjKu9dyfzbpAYe"
        assert result.currency == "EUR"
        assert result.limit == 500000

    def test_lowercase_currency_normalized(self):
        result = parse_trustline("0:1:usd:1000")
        assert result.currency == "USD"

    def test_hex_currency_preserved(self):
        hex_currency = "0" * 40  # 40 hex chars
        result = parse_trustline(f"0:1:{hex_currency}:1000")
        assert result.currency == hex_currency

    def test_invalid_too_few_parts(self):
        with pytest.raises(ParseError) as exc_info:
            parse_trustline("0:1:USD")
        assert "Expected 'account1:account2:currency:limit'" in str(exc_info.value)

    def test_invalid_too_many_parts(self):
        with pytest.raises(ParseError) as exc_info:
            parse_trustline("0:1:USD:1000:extra")
        assert "got 5 parts" in str(exc_info.value)

    def test_invalid_empty_account1(self):
        with pytest.raises(ParseError) as exc_info:
            parse_trustline(":1:USD:1000")
        assert "account1 cannot be empty" in str(exc_info.value)

    def test_invalid_empty_currency(self):
        with pytest.raises(ParseError) as exc_info:
            parse_trustline("0:1::1000")
        assert "currency cannot be empty" in str(exc_info.value)

    def test_invalid_currency_length(self):
        with pytest.raises(ParseError) as exc_info:
            parse_trustline("0:1:US:1000")
        assert "must be 3 characters" in str(exc_info.value)

    def test_invalid_limit_not_integer(self):
        with pytest.raises(ParseError) as exc_info:
            parse_trustline("0:1:USD:abc")
        assert "must be an integer" in str(exc_info.value)

    def test_invalid_limit_negative(self):
        with pytest.raises(ParseError) as exc_info:
            parse_trustline("0:1:USD:-1000")
        assert "must be positive" in str(exc_info.value)


class TestParseAMMPool:
    """Tests for parse_amm_pool function."""

    def test_xrp_issued_minimal(self):
        # XRP:USD:issuer:amount1:amount2
        result = parse_amm_pool("XRP:USD:0:1000000000000:1000000")
        assert result.asset1.currency is None
        assert result.asset1.issuer is None
        assert result.asset2.currency == "USD"
        assert result.asset2.issuer == "0"
        assert result.amount1 == "1000000000000"
        assert result.amount2 == "1000000"
        assert result.fee == 500  # default
        assert result.creator is None

    def test_xrp_issued_with_fee(self):
        result = parse_amm_pool("XRP:USD:0:1000000000000:1000000:300")
        assert result.fee == 300
        assert result.creator is None

    def test_xrp_issued_with_fee_and_creator(self):
        result = parse_amm_pool("XRP:USD:0:1000000000000:1000000:500:1")
        assert result.fee == 500
        assert result.creator == "1"

    def test_issued_issued(self):
        # USD:issuer1:EUR:issuer2:amount1:amount2
        result = parse_amm_pool("USD:0:EUR:1:1000000:500000")
        assert result.asset1.currency == "USD"
        assert result.asset1.issuer == "0"
        assert result.asset2.currency == "EUR"
        assert result.asset2.issuer == "1"
        assert result.amount1 == "1000000"
        assert result.amount2 == "500000"

    def test_xrp_case_insensitive(self):
        result = parse_amm_pool("xrp:USD:0:1000:1000")
        assert result.asset1.currency is None
        assert result.asset1.issuer is None

    def test_lowercase_currency_normalized(self):
        result = parse_amm_pool("XRP:usd:0:1000:1000")
        assert result.asset2.currency == "USD"

    def test_invalid_both_xrp(self):
        with pytest.raises(ParseError) as exc_info:
            parse_amm_pool("XRP:XRP:1000:1000")
        assert "Both assets cannot be XRP" in str(exc_info.value)

    def test_invalid_missing_amounts(self):
        with pytest.raises(ParseError) as exc_info:
            parse_amm_pool("XRP:USD:0:1000")
        assert "Missing amounts" in str(exc_info.value)

    def test_invalid_amount_not_number(self):
        with pytest.raises(ParseError) as exc_info:
            parse_amm_pool("XRP:USD:0:abc:1000")
        assert "Invalid amount1" in str(exc_info.value)

    def test_invalid_fee_out_of_range(self):
        with pytest.raises(ParseError) as exc_info:
            parse_amm_pool("XRP:USD:0:1000:1000:1001")
        assert "must be 0-1000" in str(exc_info.value)

    def test_invalid_fee_negative(self):
        with pytest.raises(ParseError) as exc_info:
            parse_amm_pool("XRP:USD:0:1000:1000:-1")
        assert "must be 0-1000" in str(exc_info.value)

    def test_invalid_missing_issuer(self):
        # USD:issuer:amount1 has only 3 parts, fails min parts check
        with pytest.raises(ParseError) as exc_info:
            parse_amm_pool("USD:0:1000")
        assert "Expected at least" in str(exc_info.value)

    def test_invalid_issued_issued_too_few_parts(self):
        # USD:issuer1:EUR:issuer2:amt - needs 6 parts minimum for issued/issued
        # This gets parsed as USD:0 + EUR:1000 + remaining=[500], too few amounts
        with pytest.raises(ParseError) as exc_info:
            parse_amm_pool("USD:0:EUR:1000:500")
        assert "Missing amounts" in str(exc_info.value)

    def test_with_address_issuer(self):
        addr = "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh"
        result = parse_amm_pool(f"XRP:USD:{addr}:1000:1000")
        assert result.asset2.issuer == addr


# ---------------------------------------------------------------------------
# parse_mpt_spec
# ---------------------------------------------------------------------------
class TestParseMptSpec:
    def test_minimal(self):
        result = parse_mpt_spec("0:2")
        assert result.issuer == "0"
        assert result.sequence == 2
        assert result.max_amount is None
        assert result.flags == 0
        assert result.asset_scale is None
        assert result.transfer_fee is None
        assert result.metadata is None

    def test_with_max_amount(self):
        result = parse_mpt_spec("0:2:1000000")
        assert result.max_amount == "1000000"

    def test_with_flags(self):
        result = parse_mpt_spec("0:2:1000000:64")
        assert result.flags == 64

    def test_with_asset_scale(self):
        result = parse_mpt_spec("0:2:1000000:0:2")
        assert result.asset_scale == 2

    def test_with_transfer_fee(self):
        result = parse_mpt_spec("0:2:1000000:0:0:100")
        assert result.transfer_fee == 100

    def test_with_metadata(self):
        result = parse_mpt_spec("0:2:1000000:0:0:0:48656C6C6F")
        assert result.metadata == "48656C6C6F"

    def test_metadata_uppercased(self):
        result = parse_mpt_spec("0:2:::0:0:48656c6c6f")
        assert result.metadata == "48656C6C6F"

    def test_address_as_issuer(self):
        addr = "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh"
        result = parse_mpt_spec(f"{addr}:1")
        assert result.issuer == addr

    def test_missing_sequence_raises(self):
        with pytest.raises(ParseError, match="at least"):
            parse_mpt_spec("0")

    def test_empty_string_raises(self):
        with pytest.raises(ParseError):
            parse_mpt_spec("")

    def test_invalid_sequence_raises(self):
        with pytest.raises(ParseError, match="sequence"):
            parse_mpt_spec("0:abc")

    def test_sequence_zero_raises(self):
        with pytest.raises(ParseError, match="sequence must be"):
            parse_mpt_spec("0:0")

    def test_invalid_max_amount_raises(self):
        with pytest.raises(ParseError, match="max_amount"):
            parse_mpt_spec("0:1:notanumber")

    def test_max_amount_zero_raises(self):
        with pytest.raises(ParseError, match="max_amount must be positive"):
            parse_mpt_spec("0:1:0")

    def test_invalid_asset_scale_raises(self):
        with pytest.raises(ParseError, match="asset_scale"):
            parse_mpt_spec("0:1:::abc")

    def test_asset_scale_out_of_range_raises(self):
        with pytest.raises(ParseError, match="asset_scale must be 0-255"):
            parse_mpt_spec("0:1:::256")

    def test_transfer_fee_out_of_range_raises(self):
        with pytest.raises(ParseError, match="transfer_fee must be"):
            parse_mpt_spec("0:1::::50001")

    def test_invalid_metadata_raises(self):
        with pytest.raises(ParseError, match="metadata"):
            parse_mpt_spec("0:1:::::ZZZZ")

    def test_odd_length_metadata_raises(self):
        with pytest.raises(ParseError, match="metadata"):
            parse_mpt_spec("0:1:::::ABC")

    def test_empty_optional_fields_use_defaults(self):
        """Empty colon-separated slots between required fields use defaults."""
        result = parse_mpt_spec("0:1::64")
        assert result.max_amount is None
        assert result.flags == 64
