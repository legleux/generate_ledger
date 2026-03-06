"""Ledger configuration types extracted from ledger.py for clarity."""

from dataclasses import dataclass

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass
class ExplicitTrustline:
    """Explicit trustline specification for LedgerConfig."""

    account1: str  # Account index or rAddress
    account2: str  # Account index or rAddress
    currency: str  # Currency code
    limit: int  # Trust limit


class FeeConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GL_", env_file=".env")
    base_fee_drops: int = 121
    reserve_base_drops: int = 2_000_000  # 2 XRP
    reserve_increment_drops: int = 666

    @property
    def xrpl(self) -> dict[str, str | int]:
        return {
            "LedgerEntryType": "FeeSettings",
            "BaseFeeDrops": self.base_fee_drops,
            "Flags": 0,
            "ReserveBaseDrops": self.reserve_base_drops,
            "ReserveIncrementDrops": self.reserve_increment_drops,
            "index": "4BC50C9B0D8515D3EAAE1E74B29A95804346C491EE1A95BF25E4AAB854A6A651",
        }


class MPTHolderConfig(BaseModel):
    """A single MPToken holder with a pre-funded balance."""

    holder: str  # Account index ("0") or classic address
    amount: str  # MPT amount as string (integer, no decimals)


class MPTIssuanceConfig(BaseModel):
    """Configuration for a single MPTokenIssuance ledger object."""

    issuer: str  # Account index or classic address
    sequence: int = 1  # Issuer's account sequence at issuance time
    max_amount: str | None = None  # Maximum supply (uint64 string); None = unlimited
    asset_scale: int | None = None  # Decimal precision (0-255)
    transfer_fee: int | None = None  # Transfer fee in 1/10 basis points (0-50000)
    metadata: str | None = None  # Hex-encoded metadata blob
    flags: int = 0  # MPTokenIssuance flags (e.g. tfMPTCanTransfer=0x40)
    holders: list[MPTHolderConfig] = Field(default_factory=list)


class AMMPoolConfig(BaseSettings):
    """Configuration for a single AMM pool."""

    model_config = SettingsConfigDict(env_prefix="GL_AMM_POOL_", env_file=".env")

    # Asset 1 (None values = XRP)
    asset1_currency: str | None = None
    asset1_issuer: str | None = None  # Will be resolved to account index if integer string
    asset1_amount: str = "1000000000000"  # 1M XRP in drops

    # Asset 2
    asset2_currency: str = "USD"
    asset2_issuer: str | None = None  # Will be resolved to account index if integer string
    asset2_amount: str = "1000000"

    # AMM parameters
    trading_fee: int = 500  # Basis points (500 = 0.5%)
    creator: str | None = None  # Account index or address for creator
