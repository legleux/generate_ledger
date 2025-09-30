from types import SimpleNamespace
from pathlib import Path
from typing import Optional
import typer

from generate_ledger.config import ComposeConfig, LedgerConfig
from generate_ledger.cli_defaults import (
    defaults_leaf_from_cfg,
    nest_default_map,
    merge_default_maps,
)
# ⬇️ import the generated Click command object itself
from .compose import app as compose_app, write_cmd

app = typer.Typer(help="generate_ledger CLI", no_args_is_help=False)

@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    output_file: Optional[Path] = typer.Option(None, "--output-file", "-o"),
):
    if ctx.obj is None:
        state = SimpleNamespace(
            compose=ComposeConfig(),
            ledger=LedgerConfig(),
        )
        ctx.obj = state

        compose_leaf = defaults_leaf_from_cfg(state.compose, "compose-write")
        ctx.default_map = merge_default_maps(
            nest_default_map(("compose", "write"), compose_leaf),
        )

    # No subcommand? Call the generated Click command directly.
    if ctx.invoked_subcommand is None:
        kwargs = {}
        if output_file is not None:
            kwargs["output_file"] = output_file
        # IMPORTANT: ctx.invoke works with any Click command, it doesn't need to be on the same group instance
        return ctx.invoke(write_cmd, **kwargs)

# keep the explicit sub-app
app.add_typer(compose_app, name="compose")
