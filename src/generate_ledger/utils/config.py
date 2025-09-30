from pathlib import Path
from platformdirs import user_config_path

def get_config_file(app_name: str, filename: str = "config.yaml") -> Path:
    """
    Return the per-user config file path for the given app name,
    creating the parent directory if necessary.

    Examples:
        get_config_file("generate_ledger")
        get_config_file("myapp", "settings.json")
    """
    config_file = user_config_path(app_name, appauthor=False) / filename
    config_file.parent.mkdir(parents=True, exist_ok=True)
    return config_file
