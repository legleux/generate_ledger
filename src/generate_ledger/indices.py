import hashlib
import base58
from xrpl.core.addresscodec import decode_classic_address

from gl.models.namespace import NamespaceByte, ns_prefix, ACCOUNT, TRUST_LINE, OWNER_DIR, DIR_NODE

def _sha512_half(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()[:32]

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

def owner_dir(account: str):
    preimage1 = ns_prefix(OWNER_DIR) + _decode_account_id(account)
    idx = _sha512_half(preimage1).hex().upper()
    # preimage2 = ns_prefix(DIR_NODE) + _decode_account_id(account)
    print(_sha512_half(preimage1).hex().upper())
    # print(_sha512_half(preimage2).hex().upper())
    return idx
