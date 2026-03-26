"""XRPL ledger object index calculations.

Computes deterministic SHA512Half-based indices for all ledger entry types
using XRPL's hash prefix scheme (namespace byte + payload).

Sections:
  - Account decoding
  - Currency / asset encoding
  - Generic index computation
  - AccountRoot indices
  - RippleState / trustline indices
  - Owner directory indices
  - AMM indices
  - MPT indices
"""

import struct

import base58
from xrpl.core.addresscodec import decode_classic_address, encode_classic_address

from generate_ledger.crypto import ripesha, sha512_half  # re-exported
from generate_ledger.models.namespace import (
    ACCOUNT,
    AMM,
    MPTOKEN,
    MPTOKEN_ISSUANCE,
    OWNER_DIR,
    TRUST_LINE,
    NamespaceByte,
    ns_prefix,
)

ACCOUNT_ID_BYTES = 20
STANDARD_CURRENCY_LEN = 3
HEX_CURRENCY_LEN = 40


# ---------------------------------------------------------------------------
# Account decoding
# ---------------------------------------------------------------------------


def _decode_account(address: str) -> bytes:
    """XRP Base58Check decode, drop version byte."""
    return base58.b58decode_check(address, alphabet=base58.XRP_ALPHABET)[1:]


def _decode_account_id(classic_address: str) -> bytes:
    """Classic address (Base58 'r...') -> 20-byte AccountID."""
    acct = decode_classic_address(classic_address)
    if len(acct) != ACCOUNT_ID_BYTES:
        raise ValueError("AccountID must be 20 bytes")
    return acct


# ---------------------------------------------------------------------------
# Currency / asset encoding
# ---------------------------------------------------------------------------


def _currency_to_160(code: str) -> bytes:
    """Convert a currency spec into the 20-byte 'currency' field used on trust lines.

    Accepts either:
      - a 3-letter ASCII code like "USD" (placed at bytes 12..14, others 0)
      - a 40-hex string (20 raw bytes), for non-standard/issued currencies
    """
    code = code.strip()
    if code == 0:
        raise ValueError("XRP cannot be currency")

    if all(c in "0123456789abcdefABCDEF" for c in code) and len(code) == HEX_CURRENCY_LEN:
        return bytes.fromhex(code)

    if len(code) == STANDARD_CURRENCY_LEN and code.isascii():
        b = bytearray(ACCOUNT_ID_BYTES)
        b[12:15] = code.encode("ascii")
        return bytes(b)

    raise ValueError("Currency must be a 3-letter ASCII code (e.g., 'USD') or a 40-hex string.")


def _asset_to_bytes(issuer: str | None, currency: str | None) -> bytes:
    """Convert an asset to (issuer, currency) bytes for AMM index calculation.

    For XRP: issuer=None, currency=None -> 40 zero bytes
    For issued: issuer="rXXX...", currency="USD" -> 20-byte issuer + 20-byte currency
    """
    if issuer is None and currency is None:
        return bytes(40)
    elif issuer is not None and currency is not None:
        issuer_bytes = _decode_account_id(issuer)
        currency_bytes = _currency_to_160(currency)
        return issuer_bytes + currency_bytes
    else:
        raise ValueError("Asset must have both issuer and currency, or neither (for XRP)")


# ---------------------------------------------------------------------------
# Generic index computation
# ---------------------------------------------------------------------------


def compute_index(ns: NamespaceByte, payload: bytes) -> str:
    return sha512_half(ns_prefix(ns) + payload).hex().upper()


# ---------------------------------------------------------------------------
# AccountRoot indices
# ---------------------------------------------------------------------------


def account_root_index(address: str) -> str:
    return compute_index(ACCOUNT, _decode_account(address))


# ---------------------------------------------------------------------------
# RippleState / trustline indices
# ---------------------------------------------------------------------------


def _order_low_high(a1: bytes, a2: bytes) -> tuple[bytes, bytes]:
    """Order two 20-byte AccountIDs as (low, high) by lexicographic byte ordering."""
    if len(a1) != ACCOUNT_ID_BYTES or len(a2) != ACCOUNT_ID_BYTES:
        raise ValueError("AccountIDs must be 20 bytes.")
    return (a1, a2) if a1 < a2 else (a2, a1)


def ripple_state_index(account_a: str, account_b: str, currency: str) -> str:
    a1 = _decode_account_id(account_a)
    a2 = _decode_account_id(account_b)
    low, high = _order_low_high(a1, a2)
    cur = _currency_to_160(currency)

    preimage = ns_prefix(TRUST_LINE) + low + high + cur
    return sha512_half(preimage).hex().upper()


# ---------------------------------------------------------------------------
# Owner directory indices
# ---------------------------------------------------------------------------


def owner_dir(account: str) -> str:
    """Compute the owner directory index for an account."""
    preimage = ns_prefix(OWNER_DIR) + _decode_account_id(account)
    return sha512_half(preimage).hex().upper()


# ---------------------------------------------------------------------------
# AMM indices
# ---------------------------------------------------------------------------


def amm_index(
    issuer1: str | None,
    currency1: str | None,
    issuer2: str | None,
    currency2: str | None,
) -> str:
    """Compute the AMM ledger object index from two assets.

    For XRP, pass issuer=None and currency=None.
    For issued currencies, pass the issuer address and currency code.

    Assets are ordered lexicographically by their (issuer + currency) bytes.
    """
    asset1_bytes = _asset_to_bytes(issuer1, currency1)
    asset2_bytes = _asset_to_bytes(issuer2, currency2)

    if asset1_bytes > asset2_bytes:
        asset1_bytes, asset2_bytes = asset2_bytes, asset1_bytes

    preimage = ns_prefix(AMM) + asset1_bytes + asset2_bytes
    return sha512_half(preimage).hex().upper()


def amm_account_id(
    amm_index_hex: str,
    parent_hash: bytes = bytes(32),
) -> str:
    """Derive the AMM pseudo-account address from the AMM index.

    For genesis ledger, parent_hash is 32 zero bytes.
    Returns the classic address (r...) of the AMM account.

    Formula: RIPESHA(i_u16 + parentHash + ammIndex)
    where i=0 for genesis (no collisions expected).
    """
    amm_index_bytes = bytes.fromhex(amm_index_hex)
    i_bytes = struct.pack(">H", 0)
    preimage = i_bytes + parent_hash + amm_index_bytes
    account_id = ripesha(preimage)
    return encode_classic_address(account_id)


def amm_lpt_currency(currency1: str | None, currency2: str | None) -> str:
    """Derive the LP token currency code for an AMM.

    Formula: 0x03 + first_19_bytes_of(SHA512Half(min(cur1, cur2), max(cur1, cur2)))

    This uses ONLY the currency codes (not issuers), matching xrpld's ammLPTCurrency().

    For XRP, pass currency=None (will use 20 zero bytes).
    Returns the 40-character hex string of the LP token currency.
    """
    cur1_bytes = bytes(20) if currency1 is None else _currency_to_160(currency1)
    cur2_bytes = bytes(20) if currency2 is None else _currency_to_160(currency2)

    min_cur, max_cur = (cur1_bytes, cur2_bytes) if cur1_bytes < cur2_bytes else (cur2_bytes, cur1_bytes)

    hash_result = sha512_half(min_cur + max_cur)

    lpt_currency = bytes([0x03]) + hash_result[:19]
    return lpt_currency.hex().upper()


# ---------------------------------------------------------------------------
# MPT indices
# ---------------------------------------------------------------------------


def make_mpt_id(sequence: int, issuer_address: str) -> bytes:
    """Create the 24-byte MPT issuance ID (MPTID).

    Formula (from xrpld makeMptID):
        4-byte big-endian uint32 sequence + 20-byte AccountID

    This ID is used as both the MPTokenIssuanceID field value (as 48-char hex)
    and as the preimage for computing the MPTokenIssuance ledger index.
    """
    seq_bytes = struct.pack(">I", sequence)
    account_bytes = _decode_account_id(issuer_address)
    return seq_bytes + account_bytes


def mpt_id_to_hex(sequence: int, issuer_address: str) -> str:
    """Return the 48-char uppercase hex MPTID (used as MPTokenIssuanceID field)."""
    return make_mpt_id(sequence, issuer_address).hex().upper()


def mpt_issuance_index(sequence: int, issuer_address: str) -> str:
    """Compute the MPTokenIssuance ledger object index.

    Formula (from xrpld keylet::mptIssuance):
        SHA512Half(0x007E + makeMptID(sequence, issuer))

    Namespace: MPTOKEN_ISSUANCE = '~' = 0x7E
    """
    mpt_id = make_mpt_id(sequence, issuer_address)
    return compute_index(MPTOKEN_ISSUANCE, mpt_id)


def mptoken_index(issuance_index_hex: str, holder_address: str) -> str:
    """Compute the MPToken ledger object index for a specific holder.

    Formula (from xrpld keylet::mptoken):
        SHA512Half(0x0074 + issuanceKey(32 bytes) + holderAccountID(20 bytes))

    Namespace: MPTOKEN = 't' = 0x74
    Args:
        issuance_index_hex: The MPTokenIssuance object's ledger index (64-char hex).
        holder_address:     The holder's classic address.
    """
    issuance_key = bytes.fromhex(issuance_index_hex)
    holder_bytes = _decode_account_id(holder_address)
    preimage = ns_prefix(MPTOKEN) + issuance_key + holder_bytes
    return sha512_half(preimage).hex().upper()
