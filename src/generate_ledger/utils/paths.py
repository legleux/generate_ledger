from pathlib import Path


def default_config_path() -> Path:
    return Path(user_config_dir(APP_NAME, APP_AUTHOR)) / "config.toml"

def resolve_config_path() -> Path:
    override = os.getenv(ENV_CONFIG)
    return Path(override).expanduser() if override else default_config_path()


def ensure_parent_dirs(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


def create_if_missing(p: Path, content: str = DEFAULT_TOML) -> bool:
    """Create file if it doesn't exist. Returns True if created."""
    if p.exists():
        return False
    ensure_parent_dirs(p)
    # Write text atomically-ish (best effort).
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(p)
    return True
