from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Type

import click

from generate_ledger.cli_defaults import normalized_mapping, OptMeta

# Minimal type mapper; extend if you’ve got more types in your model
_CLICK_TYPES = {
    int: click.INT,
    float: click.FLOAT,
    bool: click.BOOL,
    str: click.STRING,
    Path: click.Path(path_type=Path),
}

def _click_type_for(model_cls: Type, model_field: str) -> click.ParamType:
    # Pydantic v2
    try:
        ann = model_cls.model_fields[model_field].annotation
    except Exception:
        ann = str
    return _CLICK_TYPES.get(ann, click.STRING)

def build_command_from_defaults(
    *,
    command_name: str,
    command_key: str,                # e.g. "compose-write" -> look up in CLI_DEFAULTS
    model_cls: Type,                 # e.g. ComposeConfig
    state_attr: str,                 # e.g. "compose" (so we can read ctx.obj.compose)
    runner: Callable[[Any, dict[str, Any], Any | None], None],
    extra_options: list[click.Option] | None = None,  # non-model options (like output_file if treated specially)
) -> click.Command:
    mapping: dict[str, OptMeta] = normalized_mapping(command_key)

    params: list[click.Parameter] = []
    # Build one option per CLI key from CLI_DEFAULTS
    for cli_opt, meta in mapping.items():
        field = meta["field"]
        # Flags: support aliases if provided; else derive a long flag from the CLI key
        aliases = meta.get("aliases") or []
        long_flag = f"--{cli_opt.replace('_','-')}"
        flags = aliases + [long_flag]
        ptype = _click_type_for(model_cls, field)
        param_kwargs = {
            "type": ptype,
            "default": None,        # let ctx.default_map fill actual defaults
            "show_default": False,
        }
        if env := meta.get("env"):
            param_kwargs["envvar"] = env
        if help_text := meta.get("help"):
            param_kwargs["help"] = help_text

        params.append(click.Option(flags, **param_kwargs))
    # Allow extra non-model options if you need them
    if extra_options:
        params.extend(extra_options)

    @click.pass_context
    def callback(ctx: click.Context, **cli_values):
        # ensure state exists for direct invocation
        if ctx.obj is None:
            # only used in odd invocations; normal flow sets this in root callback
            from generate_ledger.config import ComposeConfig, LedgerConfig
            ctx.obj = SimpleNamespace(compose=ComposeConfig(), ledger=LedgerConfig())

        state = ctx.obj
        base_model = getattr(state, state_attr)

        # Split out any extra non-model options you added
        output_file = cli_values.pop("output_file", None) if "output_file" in cli_values else None

        # Map CLI values to model overrides via CLI_DEFAULTS; only keep non-None
        overrides: dict[str, Any] = {}
        for cli_opt, meta in mapping.items():
            val = cli_values.get(cli_opt)
            if val is not None:
                overrides[meta["field"]] = val

        runner(base_model, overrides, output_file)

    return click.Command(name=command_name, params=params, callback=callback)
