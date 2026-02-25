from pathlib import Path
from ruamel.yaml import YAML
from gl.utils import deep_merge
from gl.compose import ComposeConfig

def load_compose_config(
    profile_doc: dict | None = None,
    overrides: dict | None = None,
) -> ComposeConfig:
    base = ComposeConfig().model_dump(exclude={"compose_yml"})
    merged = deep_merge(base, profile_doc or {})
    merged = deep_merge(merged, overrides or {})
    return ComposeConfig.model_validate(merged)


def generate_compose_data():
    pass

def generate_compose(*, output: Path, network_name: str, rippled_image: str, nodes: int) -> None:
    print(f"I generate the compose file at {output}")
