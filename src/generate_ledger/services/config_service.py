# src/my_app/services/config_service.py
import json
import tomllib
from pathlib import Path

from platformdirs import user_config_dir

from generate_ledger.models.config import Config
from generate_ledger.utils.merging import deep_merge, parse_cli_sets
from generate_ledger.utils.paths import ensure_parent_dirs

APP_NAME = "generate_ledger"
APP_AUTHOR = "Michael Legleux"
DEFAULT_FILENAME = "config.toml"

DEFAULT_TOML = f"""# {APP_NAME} config
[general]
log_level = "INFO"
data_dir  = "~/.local/share/{APP_NAME}"

[network]
url  = "http://127.0.0.1"
rpc_port  = "5005"
ws_port  = "6006"
timeout_s = 10
"""

def default_config_path() -> Path:
    return Path(user_config_dir(APP_NAME, APP_AUTHOR)) / DEFAULT_FILENAME

def resolve_config_path(override: str | None) -> Path:
    return Path(override).expanduser() if override else default_config_path()

def ensure_config(override: str | None) -> Path:
    p = resolve_config_path(override)
    if not p.exists():
        ensure_parent_dirs(p)
        p.write_text(DEFAULT_TOML, encoding="utf-8")
    return p

def init_config(override: str | None, *, force: bool) -> Path:
    p = resolve_config_path(override)
    if p.exists() and not force:
        raise SystemExit(f"{p} already exists. Use --force to overwrite.")
    ensure_parent_dirs(p)
    p.write_text(DEFAULT_TOML, encoding="utf-8")
    return p

def load_file(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)

def select_profile(doc: dict, profile: str | None) -> dict:
    if not profile:
        return doc
    base = {k: v for k, v in doc.items() if k != "profiles"}
    prof = doc.get("profiles", {}).get(profile, {})
    base.update(prof)
    return base

def load_effective_config(*, profile: str | None, config_path: str | None, cli_sets: list[str]):
    defaults = Config().model_dump()
    file_doc = load_file(resolve_config_path(config_path))
    from_file = select_profile(file_doc, profile)
    cli_part = parse_cli_sets(cli_sets)
    merged = deep_merge(defaults, from_file)
    merged = deep_merge(merged, cli_part)
    return Config.model_validate(merged)

def validate(**kwargs) -> None:
    _ = load_effective_config(**kwargs)  # raises if invalid

def format_config(cfg: Config, *, redact: bool = True) -> str:
    data = cfg.model_dump()
    if redact:
        from ..utils.redact import redact_dict  # noqa: PLC0415
        data = redact_dict(data)
    return json.dumps(data, indent=2)
