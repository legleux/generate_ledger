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


@dataclass
class ParsedTrustline:
    """Parsed trustline specification."""
    account1: str  # Account index or rAddress
    account2: str  # Account index or rAddress
    currency: str  # Currency code
    limit: int     # Trust limit


@dataclass
class ParsedAsset:
    """Parsed asset specification."""
    currency: str | None  # None for XRP
    issuer: str | None    # None for XRP (index or address for issued)


@dataclass
class ParsedAMMPool:
    """Parsed AMM pool specification."""
    asset1: ParsedAsset
    asset2: ParsedAsset
    amount1: str          # Asset 1 amount
    amount2: str          # Asset 2 amount
    fee: int              # Trading fee in basis points
    creator: str | None   # Creator account index or address


class ParseError(ValueError):
    """Error parsing CLI format."""
    pass


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
    if len(parts) != 4:
        raise ParseError(
            f"Invalid trustline format: '{spec}'. "
            f"Expected 'account1:account2:currency:limit', got {len(parts)} parts"
        )

    account1, account2, currency, limit_str = parts

    if not account1:
        raise ParseError("account1 cannot be empty")
    if not account2:
        raise ParseError("account2 cannot be empty")
    if not currency:
        raise ParseError("currency cannot be empty")
    if len(currency) != 3 and len(currency) != 40:
        raise ParseError(
            f"Invalid currency '{currency}': must be 3 characters (standard) "
            f"or 40 hex characters (non-standard)"
        )

    try:
        limit = int(limit_str)
    except ValueError:
        raise ParseError(f"Invalid limit '{limit_str}': must be an integer")
    if limit <= 0:
        raise ParseError(f"limit must be positive, got {limit}")

    return ParsedTrustline(
        account1=account1,
        account2=account2,
        currency=currency.upper() if len(currency) == 3 else currency,
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
    if len(parts) != 2:
        raise ParseError(
            f"Invalid asset format: '{spec}'. "
            f"Expected 'XRP' or 'currency:issuer'"
        )

    currency, issuer = parts

    if not currency:
        raise ParseError("currency cannot be empty")
    if len(currency) != 3 and len(currency) != 40:
        raise ParseError(
            f"Invalid currency '{currency}': must be 3 characters (standard) "
            f"or 40 hex characters (non-standard)"
        )
    if not issuer:
        raise ParseError("issuer cannot be empty for issued currency")

    return ParsedAsset(
        currency=currency.upper() if len(currency) == 3 else currency,
        issuer=issuer,
    )


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

    # Minimum parts: asset1 + asset2 + amount1 + amount2
    # Asset can be "XRP" (1 part) or "currency:issuer" (2 parts)
    # So minimum is 4 parts (XRP:XRP:amt1:amt2) - but XRP/XRP is invalid
    # Typical: XRP:USD:issuer:amt1:amt2 = 5 parts
    # Or: USD:issuer1:EUR:issuer2:amt1:amt2 = 6 parts

    if len(parts) < 4:
        raise ParseError(
            f"Invalid AMM pool format: '{spec}'. "
            f"Expected at least 'asset1:asset2:amount1:amount2'"
        )

    idx = 0

    # Parse asset1
    if parts[idx].upper() == "XRP":
        asset1 = ParsedAsset(currency=None, issuer=None)
        idx += 1
    else:
        if idx + 1 >= len(parts):
            raise ParseError(f"Missing issuer for asset1 currency '{parts[idx]}'")
        currency = parts[idx]
        issuer = parts[idx + 1]
        if len(currency) != 3 and len(currency) != 40:
            raise ParseError(
                f"Invalid asset1 currency '{currency}': "
                f"must be 3 chars, 40 hex chars, or 'XRP'"
            )
        asset1 = ParsedAsset(
            currency=currency.upper() if len(currency) == 3 else currency,
            issuer=issuer,
        )
        idx += 2

    # Parse asset2
    if idx >= len(parts):
        raise ParseError("Missing asset2 in AMM pool spec")

    if parts[idx].upper() == "XRP":
        asset2 = ParsedAsset(currency=None, issuer=None)
        idx += 1
    else:
        if idx + 1 >= len(parts):
            raise ParseError(f"Missing issuer for asset2 currency '{parts[idx]}'")
        currency = parts[idx]
        issuer = parts[idx + 1]
        if len(currency) != 3 and len(currency) != 40:
            raise ParseError(
                f"Invalid asset2 currency '{currency}': "
                f"must be 3 chars, 40 hex chars, or 'XRP'"
            )
        asset2 = ParsedAsset(
            currency=currency.upper() if len(currency) == 3 else currency,
            issuer=issuer,
        )
        idx += 2

    # Both assets can't be XRP
    if asset1.currency is None and asset2.currency is None:
        raise ParseError("Both assets cannot be XRP")

    # Parse amounts
    remaining = parts[idx:]
    if len(remaining) < 2:
        raise ParseError(
            f"Missing amounts in AMM pool spec. "
            f"Got {len(remaining)} remaining parts after assets, need at least 2"
        )

    amount1 = remaining[0]
    amount2 = remaining[1]

    try:
        int(amount1)  # Validate it's a number
    except ValueError:
        raise ParseError(f"Invalid amount1 '{amount1}': must be a number")

    try:
        int(amount2)  # Validate it's a number
    except ValueError:
        raise ParseError(f"Invalid amount2 '{amount2}': must be a number")

    # Parse optional fee
    fee = 500  # Default: 0.5%
    if len(remaining) >= 3:
        try:
            fee = int(remaining[2])
        except ValueError:
            raise ParseError(f"Invalid fee '{remaining[2]}': must be an integer")
        if fee < 0 or fee > 1000:
            raise ParseError(f"Fee must be 0-1000 basis points, got {fee}")

    # Parse optional creator
    creator = None
    if len(remaining) >= 4:
        creator = remaining[3]
        if not creator:
            raise ParseError("Creator cannot be empty if specified")

    return ParsedAMMPool(
        asset1=asset1,
        asset2=asset2,
        amount1=amount1,
        amount2=amount2,
        fee=fee,
        creator=creator,
    )
