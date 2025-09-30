from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping, Iterable, Union, TypedDict

# You already have this (string form). Keep it working:
# CLI_DEFAULTS = { "compose-write": {"validators": "num_validators", ...}, ... }

class OptMeta(TypedDict, total=False):
    field: str           # model field name
    aliases: list[str]   # e.g. ["-v", "--validators"]
    env: str             # e.g. "GL_VALIDATORS"
    help: str            # help text override

# Types? dict[str, dict[str, Union[str, OptMeta]]]
CLI_DEFAULTS = {
  "compose-write": {
    # If you want -o/--output-file generated here, include it (with aliases/env if you like)
    "output_file": {
        "field": "compose_yml",
        "aliases": ["-o", "--output-file"],
        "help": "Write to this path"
    },
    "validators":  {
        "field": "num_validators",
        "aliases": ["-v", "--validators"],
        "env": "GL_VALIDATORS"
    },
    "validator_image": "validator_image",
    "validator_name":  "validator_name",
    "validator_version": "validator_version",
    "hubs": "num_hubs",
  },
}

# CLI_DEFAULTS: dict[str, dict[str, Union[str, OptMeta]]] = {
#     # your existing entries are fine; you can gradually upgrade them to OptMeta
#     "compose-write": {
#         "output_file": "compose_yml",
#         "validators": "num_validators",
#         "validator_image": "validator_image",
#         "validator_name": "validator_name",
#         "validator_version": "validator_version",
#         "hubs": "num_hubs",
#     },
#     # "ledger-write": {...}
# }

def _normalize(mapping: Mapping[str, Union[str, OptMeta]]) -> dict[str, OptMeta]:
    out: dict[str, OptMeta] = {}
    for opt, val in mapping.items():
        if isinstance(val, str):
            out[opt] = OptMeta(field=val)  # back-compat path
        else:
            out[opt] = val  # already OptMeta
    return out

def defaults_leaf_from_cfg(cfg: Any, command_key: str) -> dict[str, Any]:
    mapping = _normalize(CLI_DEFAULTS[command_key])
    leaf: dict[str, Any] = {}
    for cli_opt, meta in mapping.items():
        field = meta["field"]
        if hasattr(cfg, field):
            v = getattr(cfg, field)
            leaf[cli_opt] = str(v) if isinstance(v, Path) else v
    return leaf

def nest_default_map(command_path: Iterable[str], leaf: dict[str, Any]) -> dict[str, Any]:
    segs = list(command_path)
    root: dict[str, Any] = {}
    cur = root
    for i, seg in enumerate(segs):
        cur[seg] = leaf if i == len(segs) - 1 else {}
        cur = cur[seg]
    return root

def merge_default_maps(*maps: dict[str, Any]) -> dict[str, Any]:
    def _merge(a: dict, b: dict) -> dict:
        out = dict(a)
        for k, v in b.items():
            if k in out and isinstance(out[k], dict) and isinstance(v, dict):
                out[k] = _merge(out[k], v)
            else:
                out[k] = v
        return out
    m: dict[str, Any] = {}
    for d in maps:
        m = _merge(m, d)
    return m

def normalized_mapping(command_key: str) -> dict[str, OptMeta]:
    return _normalize(CLI_DEFAULTS[command_key])
