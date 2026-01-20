from pathlib import Path
import json
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from generate_ledger import ledger_builder
from gl.accounts import AccountConfig, generate_accounts, write_accounts_json
from gl.amendments import get_enabled_amendment_hashes
from gl.trustlines import TrustlineConfig, generate_trustlines
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

def gen_ledger_state(config: LedgerConfig | None = None):
    cfg = config or LedgerConfig()

    # 1. Generate accounts
    accounts = generate_accounts(cfg.account_cfg)
    write_accounts_json(accounts, cfg.base_dir / "accounts.json")

    # 2. Generate trustlines
    trustline_objects = generate_trustlines(accounts, cfg.trustlines)

    # 3. Assemble ledger with trustlines
    ledger = ledger_builder.assemble_ledger_json(
        accounts=accounts,
        fees=cfg.fee_cfg.xrpl,
        amendment_hashes=get_enabled_amendment_hashes(source=cfg.amendment_source),
        trustline_objects=trustline_objects,
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
