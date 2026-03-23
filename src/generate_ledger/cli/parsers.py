"""
Parsers for CLI colon-delimited formats.

Trustline format: account1:account2:currency:limit
  - account1/account2: Account index (e.g., "0", "1") or rAddress
  - currency: 3-char code (e.g., "USD")
  - limit: Trust limit (integer)

AMM pool format: asset1:asset2:amount1:amount2[:fee[:creator]]
  - asset1/asset2: "XRP" or "currency:issuer" (e.g., "USD:0" or "USD:rAddr...")
  - amount1/amount2: Asset amounts
  - fee: Trading fee in basis points (default: 500)
  - creator: Creator account index or address (optional)
"""

from dataclasses import dataclass

from generate_ledger.indices import HEX_CURRENCY_LEN, STANDARD_CURRENCY_LEN

TRUSTLINE_PARTS = 4
ASSET_PARTS = 2
MIN_AMM_PARTS = 4
MIN_AMM_AMOUNTS = 2
MIN_AMM_PARTS_WITH_FEE = 3
MIN_AMM_PARTS_WITH_CREATOR = 4
MAX_FEE_BPS = 1000
MIN_MPT_PARTS = 2
MAX_MPT_TRANSFER_FEE = 50000


@dataclass
class ParsedTrustline:
    """Parsed trustline specification."""

    account1: str  # Account index or rAddress
    account2: str  # Account index or rAddress
    currency: str  # Currency code
    limit: int  # Trust limit


@dataclass
class ParsedAsset:
    """Parsed asset specification."""

    currency: str | None  # None for XRP
    issuer: str | None  # None for XRP (index or address for issued)


@dataclass
class ParsedAMMPool:
    """Parsed AMM pool specification."""

    asset1: ParsedAsset
    asset2: ParsedAsset
    amount1: str  # Asset 1 amount
    amount2: str  # Asset 2 amount
    fee: int  # Trading fee in basis points
    creator: str | None  # Creator account index or address


class ParseError(ValueError):
    """Error parsing CLI format."""

    pass


@dataclass
class ParsedMPT:
    """Parsed MPT issuance specification."""

    issuer: str  # Account index or classic address
    sequence: int  # Issuer account sequence for the issuance
    max_amount: str | None = None  # Max supply as integer string; None = unlimited
    flags: int = 0  # MPTokenIssuance flags
    asset_scale: int | None = None  # Decimal scale (0-255)
    transfer_fee: int | None = None  # Transfer fee in 1/10 basis points (0-50000)
    metadata: str | None = None  # Hex-encoded metadata blob


def parse_trustline(spec: str) -> ParsedTrustline:
    """
    Parse a trustline specification.

    Format: account1:account2:currency:limit

    Examples:
        "0:1:USD:1000000000"          - Account index 0 to 1, USD, 1B limit
        "rAbc...:rDef...:EUR:500000"  - Using addresses directly

    Args:
        spec: Colon-delimited trustline specification

    Returns:
        ParsedTrustline with parsed fields

    Raises:
        ParseError: If the format is invalid
    """
    parts = spec.split(":")
    if len(parts) != TRUSTLINE_PARTS:
        raise ParseError(
            f"Invalid trustline format: '{spec}'. Expected 'account1:account2:currency:limit', got {len(parts)} parts"
        )

    account1, account2, currency, limit_str = parts

    if not account1:
        raise ParseError("account1 cannot be empty")
    if not account2:
        raise ParseError("account2 cannot be empty")
    if not currency:
        raise ParseError("currency cannot be empty")
    if len(currency) != STANDARD_CURRENCY_LEN and len(currency) != HEX_CURRENCY_LEN:
        raise ParseError(
            f"Invalid currency '{currency}': must be 3 characters (standard) or 40 hex characters (non-standard)"
        )

    try:
        limit = int(limit_str)
    except ValueError as e:
        raise ParseError(f"Invalid limit '{limit_str}': must be an integer") from e
    if limit <= 0:
        raise ParseError(f"limit must be positive, got {limit}")

    return ParsedTrustline(
        account1=account1,
        account2=account2,
        currency=currency.upper() if len(currency) == STANDARD_CURRENCY_LEN else currency,
        limit=limit,
    )


def _parse_asset(spec: str) -> ParsedAsset:
    """
    Parse an asset specification.

    Format: "XRP" or "currency:issuer"

    Examples:
        "XRP"           - Native XRP
        "USD:0"         - USD issued by account index 0
        "EUR:rAddr..."  - EUR issued by address

    Args:
        spec: Asset specification

    Returns:
        ParsedAsset

    Raises:
        ParseError: If the format is invalid
    """
    if spec.upper() == "XRP":
        return ParsedAsset(currency=None, issuer=None)

    parts = spec.split(":", 1)
    if len(parts) != ASSET_PARTS:
        raise ParseError(f"Invalid asset format: '{spec}'. Expected 'XRP' or 'currency:issuer'")

    currency, issuer = parts

    if not currency:
        raise ParseError("currency cannot be empty")
    if len(currency) != STANDARD_CURRENCY_LEN and len(currency) != HEX_CURRENCY_LEN:
        raise ParseError(
            f"Invalid currency '{currency}': must be 3 characters (standard) or 40 hex characters (non-standard)"
        )
    if not issuer:
        raise ParseError("issuer cannot be empty for issued currency")

    return ParsedAsset(
        currency=currency.upper() if len(currency) == STANDARD_CURRENCY_LEN else currency,
        issuer=issuer,
    )


def _parse_asset_at(parts: list[str], idx: int, label: str) -> tuple[ParsedAsset, int]:
    """Parse an asset from parts starting at idx. Returns (asset, new_idx)."""
    if idx >= len(parts):
        raise ParseError(f"Missing {label} in AMM pool spec")
    if parts[idx].upper() == "XRP":
        return ParsedAsset(currency=None, issuer=None), idx + 1
    if idx + 1 >= len(parts):
        raise ParseError(f"Missing issuer for {label} currency '{parts[idx]}'")
    currency = parts[idx]
    if len(currency) != STANDARD_CURRENCY_LEN and len(currency) != HEX_CURRENCY_LEN:
        raise ParseError(f"Invalid {label} currency '{currency}': must be 3 chars, 40 hex chars, or 'XRP'")
    return ParsedAsset(
        currency=currency.upper() if len(currency) == STANDARD_CURRENCY_LEN else currency,
        issuer=parts[idx + 1],
    ), idx + 2


def _parse_optional_int(
    parts: list[str], idx: int, name: str, *, lo: int | None = None, hi: int | None = None
) -> int | None:
    """Parse an optional integer field from parts[idx], with optional range validation."""
    if idx >= len(parts) or not parts[idx]:
        return None
    try:
        val = int(parts[idx])
    except ValueError as e:
        raise ParseError(f"Invalid {name} '{parts[idx]}': must be an integer") from e
    if lo is not None and val < lo:
        raise ParseError(f"{name} must be >= {lo}, got {val}")
    if hi is not None and val > hi:
        raise ParseError(f"{name} must be <= {hi}, got {val}")
    return val


def parse_amm_pool(spec: str) -> ParsedAMMPool:
    """
    Parse an AMM pool specification.

    Format: asset1:asset2:amount1:amount2[:fee[:creator]]

    Where each asset is "XRP" or "currency:issuer".

    Examples:
        "XRP:USD:0:1000000000000:1000000"
            - XRP/USD pool, issuer is account 0, 1M XRP, 1M USD
        "XRP:USD:0:1000000000000:1000000:500"
            - Same with explicit 500 bp (0.5%) fee
        "XRP:USD:0:1000000000000:1000000:500:1"
            - Same with account 1 as creator
        "USD:0:EUR:1:1000000:1000000"
            - Issued/issued pool: USD(issuer 0) / EUR(issuer 1)

    Args:
        spec: Colon-delimited AMM pool specification

    Returns:
        ParsedAMMPool with parsed fields

    Raises:
        ParseError: If the format is invalid
    """
    parts = spec.split(":")
    if len(parts) < MIN_AMM_PARTS:
        raise ParseError(f"Invalid AMM pool format: '{spec}'. Expected at least 'asset1:asset2:amount1:amount2'")

    asset1, idx = _parse_asset_at(parts, 0, "asset1")
    asset2, idx = _parse_asset_at(parts, idx, "asset2")

    if asset1.currency is None and asset2.currency is None:
        raise ParseError("Both assets cannot be XRP")

    remaining = parts[idx:]
    if len(remaining) < ASSET_PARTS:
        raise ParseError(
            f"Missing amounts in AMM pool spec. Got {len(remaining)} remaining parts after assets, need at least 2"
        )

    amount1 = remaining[0]
    amount2 = remaining[1]
    for val, name in [(amount1, "amount1"), (amount2, "amount2")]:
        try:
            int(val)
        except ValueError as e:
            raise ParseError(f"Invalid {name} '{val}': must be a number") from e

    fee = _parse_optional_int(remaining, 2, "fee", lo=0, hi=MAX_FEE_BPS) or 500
    creator = remaining[3] if len(remaining) >= MIN_AMM_PARTS_WITH_CREATOR and remaining[3] else None
    if len(remaining) >= MIN_AMM_PARTS_WITH_CREATOR and not remaining[3]:
        raise ParseError("Creator cannot be empty if specified")

    return ParsedAMMPool(
        asset1=asset1,
        asset2=asset2,
        amount1=amount1,
        amount2=amount2,
        fee=fee,
        creator=creator,
    )


def parse_mpt_spec(spec: str) -> ParsedMPT:
    """
    Parse an MPT issuance specification.

    Format: issuer:sequence[:max_amount[:flags[:asset_scale[:transfer_fee[:metadata]]]]]

    Examples:
        "0:2"                        - Account 0, sequence 2, unlimited supply
        "0:2:1000000"                - Max supply of 1,000,000
        "0:2:1000000:64"             - With flags=64 (tfMPTCanTransfer)
        "0:2:1000000:64:2"           - With asset_scale=2 (2 decimal places)
        "0:2:1000000:64:2:100"       - With transfer_fee=100 (10 basis points)
        "0:2:1000000:64:2:100:48656C6C6F"  - With hex metadata

    Args:
        spec: Colon-delimited MPT issuance specification

    Returns:
        ParsedMPT with parsed fields

    Raises:
        ParseError: If the format is invalid
    """
    parts = spec.split(":")
    if len(parts) < MIN_MPT_PARTS:
        raise ParseError(f"Invalid MPT format: '{spec}'. Expected at least 'issuer:sequence', got {len(parts)} part(s)")

    issuer = parts[0]
    if not issuer:
        raise ParseError("issuer cannot be empty")

    sequence = _parse_optional_int(parts, 1, "sequence", lo=1)
    if sequence is None:
        raise ParseError(f"Invalid sequence '{parts[1]}': must be an integer")

    max_amount_val = _parse_optional_int(parts, 2, "max_amount", lo=1)
    max_amount = parts[2] if max_amount_val is not None else None

    flags = _parse_optional_int(parts, 3, "flags") or 0
    asset_scale = _parse_optional_int(parts, 4, "asset_scale", lo=0, hi=255)
    transfer_fee = _parse_optional_int(parts, 5, "transfer_fee", lo=0, hi=MAX_MPT_TRANSFER_FEE)

    metadata: str | None = None
    if len(parts) > 6 and parts[6]:  # noqa: PLR2004
        metadata = parts[6].upper()
        if len(metadata) % 2 != 0 or not all(c in "0123456789ABCDEF" for c in metadata):
            raise ParseError(f"metadata must be a valid hex string, got '{parts[6]}'")

    return ParsedMPT(
        issuer=issuer,
        sequence=sequence,
        max_amount=max_amount,
        flags=flags,
        asset_scale=asset_scale,
        transfer_fee=transfer_fee,
        metadata=metadata,
    )


def build_amm_pool_config(spec: ParsedAMMPool):
    """Convert a ParsedAMMPool to AMMPoolConfig. Avoids duplicating this logic across CLI commands."""
    from generate_ledger.ledger import AMMPoolConfig  # noqa: PLC0415

    return AMMPoolConfig(
        asset1_currency=spec.asset1.currency,
        asset1_issuer=spec.asset1.issuer,
        asset1_amount=spec.amount1,
        asset2_currency=spec.asset2.currency,
        asset2_issuer=spec.asset2.issuer,
        asset2_amount=spec.amount2,
        trading_fee=spec.fee,
        creator=spec.creator,
    )
