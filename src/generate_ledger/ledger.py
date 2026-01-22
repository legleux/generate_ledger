from pathlib import Path
import json
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from generate_ledger import ledger_builder
from gl.accounts import Account, AccountConfig, generate_accounts, write_accounts_json
from gl.amendments import get_enabled_amendment_hashes
from gl.trustlines import TrustlineConfig, generate_trustlines
from gl.amm import AMMConfig, AMMSpec, Asset, generate_amm_objects
from gl import data_dir

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
    amm_pools: list[AMMPoolConfig] = Field(default_factory=list)

    base_dir: Path = Field(default=Path("testnet")) # Override with env var GL_BASE_DIR
    ledger_state_json_file: str = "ledger_state.json"
    ledger_json_file: str = "ledger.json"
    amendment_source: str = f"{data_dir / 'amendment_list_dev_20250907.json'}"

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

    # 2. Generate trustlines
    trustline_objects = generate_trustlines(accounts, cfg.trustlines)

    # 3. Generate AMM pools
    amm_specs = _build_amm_specs(cfg.amm_pools, accounts)
    amm_objects = [generate_amm_objects(spec) for spec in amm_specs] if amm_specs else None

    # 4. Assemble ledger with trustlines and AMMs
    ledger = ledger_builder.assemble_ledger_json(
        accounts=accounts,
        fees=cfg.fee_cfg.xrpl,
        amendment_hashes=get_enabled_amendment_hashes(source=cfg.amendment_source),
        trustline_objects=trustline_objects,
        amm_objects=amm_objects,
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
