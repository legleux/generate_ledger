import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

from generate_ledger import ledger_builder
from gl import data_dir
from gl.accounts import Account, AccountConfig, generate_accounts, write_accounts_json
from gl.amendments import get_enabled_amendment_hashes
from gl.amm import AMMSpec, Asset, generate_amm_objects
from gl.gateways import GatewayConfig, generate_gateway_trustlines
from gl.trustlines import TrustlineConfig, TrustlineObjects, generate_trustline_objects, generate_trustlines


@dataclass
class ExplicitTrustline:
    """Explicit trustline specification for LedgerConfig."""
    account1: str  # Account index or rAddress
    account2: str  # Account index or rAddress
    currency: str  # Currency code
    limit: int     # Trust limit

class FeeConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GL_", env_file=".env")
    base_fee_drops: int = 121
    reserve_base_drops: int = 2_000_000  # 2 XRP
    reserve_increment_drops: int = 666

    @property
    def xrpl(self) -> dict[str, str|int]:
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
    holder: str   # Account index ("0") or classic address
    amount: str   # MPT amount as string (integer, no decimals)


class MPTIssuanceConfig(BaseModel):
    """Configuration for a single MPTokenIssuance ledger object."""
    issuer: str                           # Account index or classic address
    sequence: int = 1                     # Issuer's account sequence at issuance time
    max_amount: str | None = None         # Maximum supply (uint64 string); None = unlimited
    asset_scale: int | None = None        # Decimal precision (0-255)
    transfer_fee: int | None = None       # Transfer fee in 1/10 basis points (0-50000)
    metadata: str | None = None           # Hex-encoded metadata blob
    flags: int = 0                        # MPTokenIssuance flags (e.g. tfMPTCanTransfer=0x40)
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


class LedgerConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GL_",              # Use GL_* variables to set defaults from environment
        env_file=".env",
        env_nested_delimiter="__",     # Format to set individual components from env GL_ACCOUNT__NUM_ACCOUNTS, etc.
        extra="ignore",
    )
    account_cfg: AccountConfig = Field(default_factory=AccountConfig)
    fee_cfg: FeeConfig = Field(default_factory=FeeConfig)
    trustlines: TrustlineConfig = Field(default_factory=TrustlineConfig)
    explicit_trustlines: list[ExplicitTrustline] = Field(default_factory=list)
    gateway_cfg: GatewayConfig = Field(default_factory=GatewayConfig)
    amm_pools: list[AMMPoolConfig] = Field(default_factory=list)
    mpt_issuances: list[MPTIssuanceConfig] = Field(default_factory=list)

    base_dir: Path = Field(default=Path("testnet")) # Override with env var GL_BASE_DIR
    ledger_state_json_file: str = "ledger_state.json"
    ledger_json_file: str = "ledger.json"

    # Legacy amendment source (backward-compatible)
    amendment_source: str = f"{data_dir / 'amendment_list_dev_20250907.json'}"

    # New profile-based amendment system
    amendment_profile: str | None = None  # "release", "develop", "custom" — None = legacy
    amendment_profile_source: str | None = None  # Path to features.macro or custom JSON
    enable_amendments: list[str] = Field(default_factory=list)
    disable_amendments: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def ledger_json(self) -> Path:
        return self.base_dir / self.ledger_json_file

    @computed_field
    @property
    def ledger_state_json(self) -> Path:
        return self.base_dir / self.ledger_state_json_file

def gen_fees_state(config: FeeConfig | None = None) -> dict[str, str|int]:
    cfg = config or FeeConfig()
    return cfg.to_xrpl()


def _resolve_account_ref(ref: str | None, accounts: list[Account]) -> str | None:
    """
    Resolve an account reference to an address.

    If ref is a digit string (e.g., "0", "1"), treat it as an index into accounts.
    Otherwise, return it as-is (assuming it's an address).
    """
    if ref is None:
        return None
    if ref.isdigit():
        idx = int(ref)
        if 0 <= idx < len(accounts):
            return accounts[idx].address
        raise ValueError(f"Account index {idx} out of range (have {len(accounts)} accounts)")
    return ref


def _resolve_account_to_object(ref: str, accounts: list[Account]) -> Account:
    """
    Resolve an account reference to an Account object.

    If ref is a digit string (e.g., "0", "1"), treat it as an index into accounts.
    Otherwise, search by address.
    """
    if ref.isdigit():
        idx = int(ref)
        if 0 <= idx < len(accounts):
            return accounts[idx]
        raise ValueError(f"Account index {idx} out of range (have {len(accounts)} accounts)")

    # Search by address
    for acct in accounts:
        if acct.address == ref:
            return acct
    raise ValueError(f"Account with address '{ref}' not found in accounts list")


def _build_explicit_trustlines(
    parsed_trustlines: list[ExplicitTrustline],
    accounts: list[Account],
    ledger_seq: int = 2,
) -> list[TrustlineObjects]:
    """Build TrustlineObjects from parsed trustline specifications."""
    result = []
    for spec in parsed_trustlines:
        account_a = _resolve_account_to_object(spec.account1, accounts)
        account_b = _resolve_account_to_object(spec.account2, accounts)

        tl_objects = generate_trustline_objects(
            account_a=account_a,
            account_b=account_b,
            currency=spec.currency,
            limit=spec.limit,
            ledger_seq=ledger_seq,
        )
        result.append(tl_objects)
    return result


def _build_amm_specs(pool_configs: list[AMMPoolConfig], accounts: list[Account]) -> list[AMMSpec]:
    """Build AMMSpec objects from pool configurations, resolving account references."""
    specs = []
    for pool_cfg in pool_configs:
        # Resolve issuers
        issuer1 = _resolve_account_ref(pool_cfg.asset1_issuer, accounts)
        issuer2 = _resolve_account_ref(pool_cfg.asset2_issuer, accounts)

        # Resolve creator
        creator_addr = _resolve_account_ref(pool_cfg.creator, accounts)
        creator = None
        if creator_addr:
            # Find the Account object for the creator
            for acct in accounts:
                if acct.address == creator_addr:
                    creator = acct
                    break

        spec = AMMSpec(
            asset1=Asset(
                currency=pool_cfg.asset1_currency,
                issuer=issuer1,
                amount=pool_cfg.asset1_amount,
            ),
            asset2=Asset(
                currency=pool_cfg.asset2_currency,
                issuer=issuer2,
                amount=pool_cfg.asset2_amount,
            ),
            trading_fee=pool_cfg.trading_fee,
            creator=creator,
        )
        specs.append(spec)
    return specs


def gen_ledger_state(config: LedgerConfig | None = None):
    cfg = config or LedgerConfig()

    # 1. Generate accounts
    accounts = generate_accounts(cfg.account_cfg)
    write_accounts_json(accounts, cfg.base_dir / "accounts.json")

    # 2. Generate random trustlines
    trustline_objects = generate_trustlines(accounts, cfg.trustlines)

    # 3. Generate explicit trustlines
    explicit_tl_objects = _build_explicit_trustlines(
        cfg.explicit_trustlines, accounts, cfg.trustlines.ledger_seq
    )
    trustline_objects.extend(explicit_tl_objects)

    # 3.5. Generate gateway topology trustlines
    gateway_tl_objects, gateway_issuers = generate_gateway_trustlines(accounts, cfg.gateway_cfg)
    trustline_objects.extend(gateway_tl_objects)

    # 4. Generate AMM pools and collect issuer addresses
    amm_specs = _build_amm_specs(cfg.amm_pools, accounts)
    amm_objects = [generate_amm_objects(spec) for spec in amm_specs] if amm_specs else None

    # Collect issuers that need lsfDefaultRipple flag (AMM issuers + gateways)
    amm_issuers: set[str] = set()
    amm_issuers.update(gateway_issuers)
    for spec in amm_specs:
        if spec.asset1.issuer:
            amm_issuers.add(spec.asset1.issuer)
        if spec.asset2.issuer:
            amm_issuers.add(spec.asset2.issuer)

    # 5. Get amendment hashes (profile-based or legacy)
    amendment_hashes = get_enabled_amendment_hashes(
        source=cfg.amendment_source,
        profile=cfg.amendment_profile,
        amendment_source=cfg.amendment_profile_source,
        enable=cfg.enable_amendments or None,
        disable=cfg.disable_amendments or None,
    )

    # 6. Discover and invoke develop object builders (if develop/ is present)
    extra_objects: list[dict] = []
    try:
        from gl.develop import get_develop_builders  # noqa: PLC0415
        builders = get_develop_builders()
        if builders:
            from gl.amendments import get_amendments_for_profile  # noqa: PLC0415
            enabled_names = {
                a.name
                for a in get_amendments_for_profile(
                    profile=cfg.amendment_profile or "release",
                    source=cfg.amendment_profile_source,
                )
                if a.enabled
            }
            for builder_info in builders.values():
                required = builder_info.get("required_amendment")
                if required is None or required in enabled_names:
                    objects = builder_info["builder"](accounts=accounts, config=cfg)
                    extra_objects.extend(objects)
    except ImportError:
        pass  # develop/ not present (release branch) — graceful no-op

    # 7. Assemble ledger with trustlines, AMMs, and extra objects
    ledger = ledger_builder.assemble_ledger_json(
        accounts=accounts,
        fees=cfg.fee_cfg.xrpl,
        amendment_hashes=amendment_hashes,
        trustline_objects=trustline_objects,
        amm_objects=amm_objects,
        amm_issuers=amm_issuers,
        extra_objects=extra_objects if extra_objects else None,
    )
    return ledger

def write_ledger_file(output_file: Path | None = None, config: LedgerConfig | None = None) -> Path:
    cfg = config or LedgerConfig()
    output_file = Path(output_file or cfg.ledger_json)
    output_file.parent.mkdir(exist_ok=True, parents=True)
    print(f"Writing {cfg.ledger_json.name} to {output_file.resolve()}")
    ledger_data = gen_ledger_state(cfg)
    with output_file.open("w", encoding="UTF-8") as ld:
        json.dump(ledger_data, ld)
    return output_file.resolve()
