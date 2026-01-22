import hashlib
import struct
import base58
from xrpl.core.addresscodec import decode_classic_address, encode_classic_address

from gl.models.namespace import NamespaceByte, ns_prefix, ACCOUNT, TRUST_LINE, OWNER_DIR, DIR_NODE, AMM


def _sha512_half(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()[:32]


def _ripesha(data: bytes) -> bytes:
    """RIPEMD160(SHA256(data)) - used for account ID derivation."""
    sha256_hash = hashlib.sha256(data).digest()
    ripemd160 = hashlib.new('ripemd160')
    ripemd160.update(sha256_hash)
    return ripemd160.digest()

def _decode_account(address: str) -> bytes:
    # XRP Base58Check decode, drop version byte
    return base58.b58decode_check(address, alphabet=base58.XRP_ALPHABET)[1:]

def _decode_account_id(classic_address: str) -> bytes:
    # or use xply-py version?
    """Classic address (Base58 'r...') -> 20-byte AccountID."""
    acct = decode_classic_address(classic_address)
    if len(acct) != 20:
        raise ValueError("AccountID must be 20 bytes")
    return acct

def compute_index(ns: NamespaceByte, payload: bytes) -> str:
    return _sha512_half(ns_prefix(ns) + payload).hex().upper()

def account_root_index(address: str) -> str:
    return compute_index(ACCOUNT, _decode_account(address))

def _order_low_high(a1: bytes, a2: bytes) -> tuple[bytes, bytes]:
    """Order two 20-byte AccountIDs as (low, high) by lexicographic byte ordering."""
    if len(a1) != 20 or len(a2) != 20:
        raise ValueError("AccountIDs must be 20 bytes.")
    return (a1, a2) if a1 < a2 else (a2, a1)

def _currency_to_160(code: str) -> bytes:
    """
    Convert a currency spec into the 20-byte 'currency' field used on trust lines.

    Accepts either:
      - a 3-letter ASCII code like "USD" (placed at bytes 12..14, others 0)
      - a 40-hex string (20 raw bytes), for non-standard/issued currencies
    """
    code = code.strip()
    if code == 0:
        raise ValueError("XRP cannot be currency")

    # Is it hex form?
    if all(c in "0123456789abcdefABCDEF" for c in code) and len(code) == 40:
        return bytes.fromhex(code)

    # Standard 3-letter form
    if len(code) == 3 and code.isascii():
        b = bytearray(20)
        b[12:15] = code.encode("ascii")
        return bytes(b)

    raise ValueError("Currency must be a 3-letter ASCII code (e.g., 'USD') or a 40-hex string.")

def currency_code_to_bytes(code: str) -> bytes:
    """Convert an XRPL currency code (<=20 bytes) to its 160-bit representation."""
    b = code.encode("ascii")
    if len(b) > 20:
        raise ValueError("Currency code too long (max 20 bytes)")
    return b.ljust(20, b"\x00")

def currency_code_to_hex(code: str) -> str:
    return currency_code_to_bytes(code).hex().upper()

def ripple_state_index(account_a: str, account_b: str, currency: str) -> str:
    a1 = _decode_account_id(account_a)
    a2 = _decode_account_id(account_b)
    low, high = _order_low_high(a1, a2)
    cur = _currency_to_160(currency)

    # prefix = TRUST_LINE.ns_prefix()  # RippleState space key 0x0072
    preimage = ns_prefix(TRUST_LINE) + low + high + cur
    return _sha512_half(preimage).hex().upper()

def owner_dir(account: str) -> str:
    """Compute the owner directory index for an account."""
    preimage = ns_prefix(OWNER_DIR) + _decode_account_id(account)
    return _sha512_half(preimage).hex().upper()


def _asset_to_bytes(issuer: str | None, currency: str | None) -> bytes:
    """
    Convert an asset to (issuer, currency) bytes for AMM index calculation.

    For XRP: issuer=None, currency=None -> 40 zero bytes
    For issued: issuer="rXXX...", currency="USD" -> 20-byte issuer + 20-byte currency
    """
    if issuer is None and currency is None:
        # XRP: 20 zero bytes for issuer + 20 zero bytes for currency
        return bytes(40)
    elif issuer is not None and currency is not None:
        issuer_bytes = _decode_account_id(issuer)
        currency_bytes = _currency_to_160(currency)
        return issuer_bytes + currency_bytes
    else:
        raise ValueError("Asset must have both issuer and currency, or neither (for XRP)")


def amm_index(
    issuer1: str | None, currency1: str | None,
    issuer2: str | None, currency2: str | None,
) -> str:
    """
    Compute the AMM ledger object index from two assets.

    For XRP, pass issuer=None and currency=None.
    For issued currencies, pass the issuer address and currency code.

    Assets are ordered lexicographically by their (issuer + currency) bytes.
    """
    asset1_bytes = _asset_to_bytes(issuer1, currency1)
    asset2_bytes = _asset_to_bytes(issuer2, currency2)

    # Order lexicographically
    if asset1_bytes > asset2_bytes:
        asset1_bytes, asset2_bytes = asset2_bytes, asset1_bytes

    preimage = ns_prefix(AMM) + asset1_bytes + asset2_bytes
    return _sha512_half(preimage).hex().upper()


def amm_account_id(
    amm_index_hex: str,
    parent_hash: bytes = bytes(32),
) -> str:
    """
    Derive the AMM pseudo-account address from the AMM index.

    For genesis ledger, parent_hash is 32 zero bytes.
    Returns the classic address (r...) of the AMM account.

    Formula: RIPESHA(SHA512Half(i_u16 + parentHash + ammIndex))
    where i=0 for genesis (no collisions possible).
    """
    amm_index_bytes = bytes.fromhex(amm_index_hex)
    # i=0 as uint16 little-endian (matching C++ behavior)
    i_bytes = struct.pack('<H', 0)
    preimage = i_bytes + parent_hash + amm_index_bytes
    hash_result = _sha512_half(preimage)
    account_id = _ripesha(hash_result)
    return encode_classic_address(account_id)


def amm_lpt_currency(currency1: str | None, currency2: str | None) -> str:
    """
    Derive the LP token currency code for an AMM.

    Formula: 0x03 + first_19_bytes_of(SHA512Half(min(cur1, cur2), max(cur1, cur2)))

    For XRP, pass currency=None (will use 20 zero bytes).
    Returns the 40-character hex string of the LP token currency.
    """
    # Convert currencies to 160-bit representation
    cur1_bytes = bytes(20) if currency1 is None else _currency_to_160(currency1)
    cur2_bytes = bytes(20) if currency2 is None else _currency_to_160(currency2)

    # Order by minmax
    min_cur, max_cur = (cur1_bytes, cur2_bytes) if cur1_bytes < cur2_bytes else (cur2_bytes, cur1_bytes)

    # SHA512Half of concatenated currencies
    hash_result = _sha512_half(min_cur + max_cur)

    # LP token currency = 0x03 + first 19 bytes of hash
    lpt_currency = bytes([0x03]) + hash_result[:19]
    return lpt_currency.hex().upper()
