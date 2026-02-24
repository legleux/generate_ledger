def deep_merge(base: dict, override: dict) -> dict:
    """Deep-merge override into base and return base."""
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_merge(base[k], v)
        else:
            base[k] = v
    return base
