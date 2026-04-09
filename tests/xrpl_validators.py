"""XRPL ledger object validators.

Structural and semantic assertion helpers for verifying ledger objects
in tests. Each function raises AssertionError with a descriptive message.
"""

from xrpl.core.addresscodec import decode_classic_address

from generate_ledger.constants import NEUTRAL_ISSUER

LSF_AMM_NODE = 0x01000000


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _assert_hex64(value: str, field_name: str) -> None:
    """Assert value is a 64-character hex string."""
    assert isinstance(value, str), f"{field_name}: expected str, got {type(value).__name__}"
    assert len(value) == 64, f"{field_name}: expected 64 chars, got {len(value)}"
    try:
        int(value, 16)
    except ValueError as err:
        raise AssertionError(f"{field_name}: not valid hex: {value!r}") from err


def _assert_prev_txn(obj: dict) -> None:
    """Assert PreviousTxnID and PreviousTxnLgrSeq are present and valid."""
    _assert_hex64(obj["PreviousTxnID"], "PreviousTxnID")
    assert isinstance(obj["PreviousTxnLgrSeq"], int), (
        f"PreviousTxnLgrSeq: expected int, got {type(obj['PreviousTxnLgrSeq']).__name__}"
    )


# ---------------------------------------------------------------------------
# Public validators
# ---------------------------------------------------------------------------


def assert_valid_ripple_state(obj: dict) -> None:
    """Validate a RippleState ledger object."""
    assert obj["LedgerEntryType"] == "RippleState", (
        f"LedgerEntryType: expected 'RippleState', got {obj['LedgerEntryType']!r}"
    )
    _assert_hex64(obj["index"], "index")
    _assert_prev_txn(obj)

    # Low/High ordering by raw AccountID bytes (NOT base58 string comparison)
    lo_addr = obj["LowLimit"]["issuer"]
    hi_addr = obj["HighLimit"]["issuer"]
    assert decode_classic_address(lo_addr) < decode_classic_address(hi_addr), (
        f"Low/High ordering wrong: LowLimit.issuer={lo_addr} must sort before "
        f"HighLimit.issuer={hi_addr} by decoded AccountID bytes"
    )

    # Balance issuer must be the neutral issuer
    assert obj["Balance"]["issuer"] == NEUTRAL_ISSUER, (
        f"Balance.issuer: expected {NEUTRAL_ISSUER!r}, got {obj['Balance']['issuer']!r}"
    )

    # Currency consistency across all three amount fields
    currency = obj["Balance"]["currency"]
    assert obj["LowLimit"]["currency"] == currency, (
        f"LowLimit.currency mismatch: {obj['LowLimit']['currency']!r} != Balance.currency {currency!r}"
    )
    assert obj["HighLimit"]["currency"] == currency, (
        f"HighLimit.currency mismatch: {obj['HighLimit']['currency']!r} != Balance.currency {currency!r}"
    )

    # AMM trustlines: if lsfAMMNode is set, both limits must be "0"
    if obj["Flags"] & LSF_AMM_NODE:
        assert obj["HighLimit"]["value"] == "0", (
            f"AMM trustline HighLimit.value must be '0', got {obj['HighLimit']['value']!r}"
        )
        assert obj["LowLimit"]["value"] == "0", (
            f"AMM trustline LowLimit.value must be '0', got {obj['LowLimit']['value']!r}"
        )


def assert_valid_directory_node(obj: dict) -> None:
    """Validate a DirectoryNode ledger object."""
    assert obj["LedgerEntryType"] == "DirectoryNode", (
        f"LedgerEntryType: expected 'DirectoryNode', got {obj['LedgerEntryType']!r}"
    )

    indexes = obj["Indexes"]
    assert isinstance(indexes, list), f"Indexes: expected list, got {type(indexes).__name__}"
    for i, idx in enumerate(indexes):
        _assert_hex64(idx, f"Indexes[{i}]")
    assert indexes == sorted(indexes), f"Indexes not sorted: {indexes}"

    assert obj["Owner"].startswith("r"), f"Owner must start with 'r', got {obj['Owner']!r}"
    assert obj["RootIndex"] == obj["index"], f"RootIndex ({obj['RootIndex']}) != index ({obj['index']})"


def assert_valid_account_root(obj: dict) -> None:
    """Validate an AccountRoot ledger object."""
    assert obj["LedgerEntryType"] == "AccountRoot", (
        f"LedgerEntryType: expected 'AccountRoot', got {obj['LedgerEntryType']!r}"
    )

    # Balance is a string of drops (may be "0")
    balance = obj["Balance"]
    assert isinstance(balance, str), f"Balance: expected str, got {type(balance).__name__}"
    int(balance)  # raises ValueError if not numeric

    assert isinstance(obj["Sequence"], int) and obj["Sequence"] >= 0, (
        f"Sequence: expected non-negative int, got {obj['Sequence']!r}"
    )
    assert isinstance(obj["OwnerCount"], int) and obj["OwnerCount"] >= 0, (
        f"OwnerCount: expected non-negative int, got {obj['OwnerCount']!r}"
    )


def assert_valid_amm(obj: dict) -> None:
    """Validate an AMM ledger object."""
    assert obj["LedgerEntryType"] == "AMM", f"LedgerEntryType: expected 'AMM', got {obj['LedgerEntryType']!r}"

    fee = obj["TradingFee"]
    assert isinstance(fee, int) and 0 <= fee <= 1000, f"TradingFee: expected int 0-1000, got {fee!r}"

    lp_currency = obj["LPTokenBalance"]["currency"]
    assert lp_currency.startswith("03"), f"LPTokenBalance.currency must start with '03', got {lp_currency!r}"

    assert obj["Account"].startswith("r"), f"AMM Account must start with 'r', got {obj['Account']!r}"
