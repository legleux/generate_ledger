import json
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from generate_ledger import ledger_builder
from generate_ledger.accounts import (
    Account,
    AccountConfig,
    generate_accounts,
    resolve_account_ref,
    resolve_account_to_object,
    write_accounts_json,
)
from generate_ledger.amendments import get_enabled_amendment_hashes
from generate_ledger.amm import AMMSpec, Asset, generate_amm_objects
from generate_ledger.gateways import GatewayConfig, generate_gateway_trustlines
from generate_ledger.ledger_types import (  # noqa: F401 (re-exported for backward compat)
    AMMPoolConfig,
    ExplicitTrustline,
    FeeConfig,
    MPTHolderConfig,
    MPTIssuanceConfig,
)
from generate_ledger.trustlines import (
    TrustlineConfig,
    TrustlineObjects,
    generate_trustline_objects,
    generate_trustlines,
)


class LedgerConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GL_",  # Use GL_* variables to set defaults from environment
        env_file=".env",
        env_nested_delimiter="__",  # Format to set individual components from env GL_ACCOUNT__NUM_ACCOUNTS, etc.
        extra="ignore",
    )
    account_cfg: AccountConfig = Field(default_factory=AccountConfig)
    fee_cfg: FeeConfig = Field(default_factory=FeeConfig)
    trustlines: TrustlineConfig = Field(default_factory=TrustlineConfig)
    explicit_trustlines: list[ExplicitTrustline] = Field(default_factory=list)
    gateway_cfg: GatewayConfig = Field(default_factory=GatewayConfig)
    amm_pools: list[AMMPoolConfig] = Field(default_factory=list)
    mpt_issuances: list[MPTIssuanceConfig] = Field(default_factory=list)

    base_dir: Path = Field(default=Path("testnet"))  # Override with env var GL_BASE_DIR
    ledger_state_json_file: str = "ledger_state.json"
    ledger_json_file: str = "ledger.json"

    # Amendment system — develop profile auto-fetches features.macro from GitHub
    amendment_profile: str = "develop"  # "release", "develop", or "custom"
    amendment_profile_source: str | None = None  # Path to features.macro or custom JSON
    enable_amendments: list[str] = Field(default_factory=list)
    disable_amendments: list[str] = Field(default_factory=list)

    @property
    def ledger_json(self) -> Path:
        return self.base_dir / self.ledger_json_file

    @property
    def ledger_state_json(self) -> Path:
        return self.base_dir / self.ledger_state_json_file


def gen_fees_state(config: FeeConfig | None = None) -> dict[str, str | int]:
    cfg = config or FeeConfig()
    return cfg.to_xrpl()


# Backward-compatible private aliases (internal use and legacy call sites)
_resolve_account_ref = resolve_account_ref
_resolve_account_to_object = resolve_account_to_object


def _build_explicit_trustlines(
    parsed_trustlines: list[ExplicitTrustline],
    accounts: list[Account],
    ledger_seq: int = 2,
) -> list[TrustlineObjects]:
    """Build TrustlineObjects from parsed trustline specifications."""
    result = []
    for spec in parsed_trustlines:
        account_a = resolve_account_to_object(spec.account1, accounts)
        account_b = resolve_account_to_object(spec.account2, accounts)

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
        issuer1 = resolve_account_ref(pool_cfg.asset1_issuer, accounts)
        issuer2 = resolve_account_ref(pool_cfg.asset2_issuer, accounts)

        # Resolve creator
        creator_addr = resolve_account_ref(pool_cfg.creator, accounts)
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


def _collect_amm_issuers(amm_specs: list[AMMSpec], gateway_issuers: set[str]) -> set[str]:
    """Collect all issuer addresses that need lsfDefaultRipple (AMM issuers + gateways)."""
    issuers: set[str] = set(gateway_issuers)
    for spec in amm_specs:
        if spec.asset1.issuer:
            issuers.add(spec.asset1.issuer)
        if spec.asset2.issuer:
            issuers.add(spec.asset2.issuer)
    return issuers


def _load_develop_objects(cfg: "LedgerConfig", accounts: list[Account]) -> list[dict]:
    """Discover and invoke develop object builders (if develop/ is present)."""
    try:
        from generate_ledger.develop import get_develop_builders  # noqa: PLC0415

        builders = get_develop_builders()
        if not builders:
            return []

        from generate_ledger.amendments import get_amendments_for_profile  # noqa: PLC0415

        enabled_names = {
            a.name
            for a in get_amendments_for_profile(
                profile=cfg.amendment_profile or "release",
                source=cfg.amendment_profile_source,
            )
            if a.enabled
        }
        objects: list[dict] = []
        for builder_info in builders.values():
            required = builder_info.get("required_amendment")
            if required is None or required in enabled_names:
                objects.extend(builder_info["builder"](accounts=accounts, config=cfg))
        return objects
    except ImportError:
        return []


def gen_ledger_state(config: LedgerConfig | None = None, *, write_accounts: bool = True) -> dict:
    """Generate a complete XRPL genesis ledger as a dict.

    Args:
        config: Ledger configuration. Uses defaults if None.
        write_accounts: If True (default), write accounts.json to base_dir.
            Set to False for pure in-memory usage.

    Returns:
        Ledger dict suitable for json.dump() or direct use.
    """
    cfg = config or LedgerConfig()

    # 1. Generate accounts
    accounts = generate_accounts(cfg.account_cfg)
    if write_accounts:
        cfg.base_dir.mkdir(parents=True, exist_ok=True)
        write_accounts_json(accounts, cfg.base_dir / "accounts.json")

    # 2. Generate random trustlines
    trustline_objects = generate_trustlines(accounts, cfg.trustlines)

    # 3. Generate explicit trustlines
    explicit_tl_objects = _build_explicit_trustlines(cfg.explicit_trustlines, accounts, cfg.trustlines.ledger_seq)
    trustline_objects.extend(explicit_tl_objects)

    # 3.5. Generate gateway topology trustlines
    gateway_tl_objects, gateway_issuers = generate_gateway_trustlines(accounts, cfg.gateway_cfg)
    trustline_objects.extend(gateway_tl_objects)

    # 4. Generate AMM pools and collect issuer addresses
    amm_specs = _build_amm_specs(cfg.amm_pools, accounts)
    amm_objects = [generate_amm_objects(spec) for spec in amm_specs] if amm_specs else None

    amm_issuers = _collect_amm_issuers(amm_specs, gateway_issuers)

    # 5. Get amendment hashes (profile-based or legacy)
    amendment_hashes = get_enabled_amendment_hashes(
        profile=cfg.amendment_profile,
        amendment_source=cfg.amendment_profile_source,
        enable=cfg.enable_amendments or None,
        disable=cfg.disable_amendments or None,
    )

    # 6. Discover and invoke develop object builders (if develop/ is present)
    extra_objects = _load_develop_objects(cfg, accounts)

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


def write_ledger_file(
    output_file: Path | None = None,
    config: LedgerConfig | None = None,
    *,
    quiet: bool = False,
) -> Path:
    """Generate a ledger and write it to disk.

    Args:
        output_file: Output path. Defaults to config.base_dir/ledger.json.
        config: Ledger configuration. Uses defaults if None.
        quiet: If True, suppress status output. Default False for CLI compat.

    Returns:
        Resolved path to the written ledger.json file.
    """
    cfg = config or LedgerConfig()
    output_file = Path(output_file or cfg.ledger_json)
    output_file.parent.mkdir(exist_ok=True, parents=True)
    if not quiet:
        print(f"Writing {cfg.ledger_json.name} to {output_file.resolve()}")
    ledger_data = gen_ledger_state(cfg)
    with output_file.open("w", encoding="UTF-8") as ld:
        json.dump(ledger_data, ld)
    return output_file.resolve()
