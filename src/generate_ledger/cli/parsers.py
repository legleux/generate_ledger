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


@dataclass
class ParsedMPT:
    """Parsed MPT issuance specification."""
    issuer: str           # Account index or classic address
    sequence: int         # Issuer account sequence for the issuance
    max_amount: str | None = None   # Max supply as integer string; None = unlimited
    flags: int = 0        # MPTokenIssuance flags
    asset_scale: int | None = None  # Decimal scale (0-255)
    transfer_fee: int | None = None  # Transfer fee in 1/10 basis points (0-50000)
    metadata: str | None = None     # Hex-encoded metadata blob


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
    if len(currency) != STANDARD_CURRENCY_LEN and len(currency) != HEX_CURRENCY_LEN:
        raise ParseError(
            f"Invalid currency '{currency}': must be 3 characters (standard) "
            f"or 40 hex characters (non-standard)"
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
        raise ParseError(
            f"Invalid asset format: '{spec}'. "
            f"Expected 'XRP' or 'currency:issuer'"
        )

    currency, issuer = parts

    if not currency:
        raise ParseError("currency cannot be empty")
    if len(currency) != STANDARD_CURRENCY_LEN and len(currency) != HEX_CURRENCY_LEN:
        raise ParseError(
            f"Invalid currency '{currency}': must be 3 characters (standard) "
            f"or 40 hex characters (non-standard)"
        )
    if not issuer:
        raise ParseError("issuer cannot be empty for issued currency")

    return ParsedAsset(
        currency=currency.upper() if len(currency) == STANDARD_CURRENCY_LEN else currency,
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

    if len(parts) < MIN_AMM_PARTS:
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
        if len(currency) != STANDARD_CURRENCY_LEN and len(currency) != HEX_CURRENCY_LEN:
            raise ParseError(
                f"Invalid asset1 currency '{currency}': "
                f"must be 3 chars, 40 hex chars, or 'XRP'"
            )
        asset1 = ParsedAsset(
            currency=currency.upper() if len(currency) == STANDARD_CURRENCY_LEN else currency,
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
        if len(currency) != STANDARD_CURRENCY_LEN and len(currency) != HEX_CURRENCY_LEN:
            raise ParseError(
                f"Invalid asset2 currency '{currency}': "
                f"must be 3 chars, 40 hex chars, or 'XRP'"
            )
        asset2 = ParsedAsset(
            currency=currency.upper() if len(currency) == STANDARD_CURRENCY_LEN else currency,
            issuer=issuer,
        )
        idx += 2

    # Both assets can't be XRP
    if asset1.currency is None and asset2.currency is None:
        raise ParseError("Both assets cannot be XRP")

    # Parse amounts
    remaining = parts[idx:]
    if len(remaining) < ASSET_PARTS:
        raise ParseError(
            f"Missing amounts in AMM pool spec. "
            f"Got {len(remaining)} remaining parts after assets, need at least 2"
        )

    amount1 = remaining[0]
    amount2 = remaining[1]

    try:
        int(amount1)  # Validate it's a number
    except ValueError as e:
        raise ParseError(f"Invalid amount1 '{amount1}': must be a number") from e

    try:
        int(amount2)  # Validate it's a number
    except ValueError as e:
        raise ParseError(f"Invalid amount2 '{amount2}': must be a number") from e

    # Parse optional fee
    fee = 500  # Default: 0.5%
    if len(remaining) >= MIN_AMM_PARTS_WITH_FEE:
        try:
            fee = int(remaining[2])
        except ValueError as e:
            raise ParseError(f"Invalid fee '{remaining[2]}': must be an integer") from e
        if fee < 0 or fee > MAX_FEE_BPS:
            raise ParseError(f"Fee must be 0-1000 basis points, got {fee}")

    # Parse optional creator
    creator = None
    if len(remaining) >= MIN_AMM_PARTS_WITH_CREATOR:
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
        raise ParseError(
            f"Invalid MPT format: '{spec}'. "
            f"Expected at least 'issuer:sequence', got {len(parts)} part(s)"
        )

    issuer = parts[0]
    if not issuer:
        raise ParseError("issuer cannot be empty")

    try:
        sequence = int(parts[1])
    except ValueError as e:
        raise ParseError(f"Invalid sequence '{parts[1]}': must be an integer") from e
    if sequence < 1:
        raise ParseError(f"sequence must be >= 1, got {sequence}")

    max_amount: str | None = None
    if len(parts) > 2 and parts[2]:  # noqa: PLR2004
        try:
            val = int(parts[2])
        except ValueError as e:
            raise ParseError(f"Invalid max_amount '{parts[2]}': must be an integer") from e
        if val <= 0:
            raise ParseError(f"max_amount must be positive, got {val}")
        max_amount = parts[2]

    flags = 0
    if len(parts) > 3 and parts[3]:  # noqa: PLR2004
        try:
            flags = int(parts[3])
        except ValueError as e:
            raise ParseError(f"Invalid flags '{parts[3]}': must be an integer") from e

    asset_scale: int | None = None
    if len(parts) > 4 and parts[4]:  # noqa: PLR2004
        try:
            asset_scale = int(parts[4])
        except ValueError as e:
            raise ParseError(f"Invalid asset_scale '{parts[4]}': must be an integer") from e
        if not 0 <= asset_scale <= 255:  # noqa: PLR2004
            raise ParseError(f"asset_scale must be 0-255, got {asset_scale}")

    transfer_fee: int | None = None
    if len(parts) > 5 and parts[5]:  # noqa: PLR2004
        try:
            transfer_fee = int(parts[5])
        except ValueError as e:
            raise ParseError(f"Invalid transfer_fee '{parts[5]}': must be an integer") from e
        if not 0 <= transfer_fee <= MAX_MPT_TRANSFER_FEE:
            raise ParseError(
                f"transfer_fee must be 0-{MAX_MPT_TRANSFER_FEE}, got {transfer_fee}"
            )

    metadata: str | None = None
    if len(parts) > 6 and parts[6]:  # noqa: PLR2004
        metadata = parts[6].upper()
        if len(metadata) % 2 != 0 or not all(c in "0123456789ABCDEF" for c in metadata):
            raise ParseError(
                f"metadata must be a valid hex string, got '{parts[6]}'"
            )

    return ParsedMPT(
        issuer=issuer,
        sequence=sequence,
        max_amount=max_amount,
        flags=flags,
        asset_scale=asset_scale,
        transfer_fee=transfer_fee,
        metadata=metadata,
    )
