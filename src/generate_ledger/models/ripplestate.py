from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RippleStateConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GL_",              # Use GL_* variables to set defaults from environment
        env_file=".env",
        env_nested_delimiter="__",     # Format to set individual components from env GL_ACCOUNT__NUM_ACCOUNTS, etc.
        extra="ignore",
    )
    # account: AccountConfig = Field(default_factory=AccountConfig)

    base_dir: Path = Field(default=Path("testnet")) # Override with env var GL_BASE_DIR
    # ledger_state_json_file: str = "ledger_state.json"
    # ledger_json_file: str = "ledger.json"

    # @computed_field
    # @property
    # def ledger_json(self) -> Path:
    #     return self.base_dir / self.ledger_json_file

    # @computed_field
    # @property
    # def ledger_state_json(self) -> Path:
    #     return self.base_dir / self.ledger_state_json_file




# def currency_to_160(code: str) -> bytes:
#     """
#     Convert a currency spec into the 20-byte 'currency' field used on trust lines.

#     Accepts either:
#       - a 3-letter ASCII code like "USD" (placed at bytes 12..14, others 0)
#       - a 40-hex string (20 raw bytes), for non-standard/issued currencies
#     """
#     code = code.strip()
#     if code == 0:
#         raise ValueError("XRP cannot be currency")

#     # Is it hex form?
#     if all(c in "0123456789abcdefABCDEF" for c in code) and len(code) == 40:
#         return bytes.fromhex(code)

#     # Standard 3-letter form
#     if len(code) == 3 and code.isascii():
#         b = bytearray(20)
#         b[12:15] = code.encode("ascii")
#         return bytes(b)

#     raise ValueError("Currency must be a 3-letter ASCII code (e.g., 'USD') or a 40-hex string.")

# def decode_account_id(classic_address: str) -> bytes:
#     """Classic address (Base58 'r...') -> 20-byte AccountID."""
#     acct = decode_classic_address(classic_address)
#     if len(acct) != 20:
#         raise ValueError("AccountID must be 20 bytes")
#     return acct


# def ripple_state_index(account_a: str, account_b: str, currency: str) -> str:
#     """
#     Compute the 256-bit ledger object index (hex string) for a RippleState (trust line).
#     `account_a` and `account_b` are classic addresses. `currency` is 3-letter or 40-hex.
#     """
#     a1 = decode_account_id(account_a)
#     a2 = decode_account_id(account_b)
#     low, high = order_low_high(a1, a2)
#     cur = currency_to_160(currency)

#     prefix = b"\x00\x72"  # RippleState space key 0x0072
#     preimage = prefix + low + high + cur
#     return sha512_half(preimage).hex().upper()


# def sha512_half(data: bytes) -> bytes:
#     """SHA-512Half: first 32 bytes of SHA-512 digest."""
#     return hashlib.sha512(data).digest()[:32]


# def currency_code_to_bytes(code: str) -> bytes:
#     """Convert an XRPL currency code (<=20 bytes) to its 160-bit representation."""
#     b = code.encode("ascii")
#     if len(b) > 20:
#         raise ValueError("Currency code too long (max 20 bytes)")
#     return b.ljust(20, b"\x00")

# def currency_code_to_hex(code: str) -> str:
#     return currency_code_to_bytes(code).hex().upper()

# def generate_trustline(hi, lo, currency, hi_amount, lo_amount):
#     flags = 131072
#     balance = {
#         "currency": currency,
#         "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",
#         "value": "0",
#     }
#     high_limit = {
#         "currency": currency,
#         "issuer": hi,
#         "value": hi_amount,
#     }
#     low_limit = {
#         "currency": currency,
#         "issuer": lo,
#         "value": lo_amount,
#     }
#     trustline = dict(
#         Balance=balance,
#         Flags=flags,
#         HighLimit=high_limit,
#         HighNode="0",
#         LedgerEntryType="RippleState",
#         LowLimit=low_limit,
#         LowNode="0",
#         PreviousTxnID="72DC4832A16946423E1B29A971A98420D803FF24BA7309DC84F362AFBF84296F",
#         PreviousTxnLgrSeq=404995,
#         index=ripple_state_index(lo, hi, currency),
#     )
#     return [trustline]
