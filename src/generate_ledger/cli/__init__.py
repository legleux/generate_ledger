from pathlib import Path
from types import SimpleNamespace

import typer

from generate_ledger.cli_defaults import (
    defaults_leaf_from_cfg,
    merge_default_maps,
    nest_default_map,
)
from generate_ledger.config import ComposeConfig, LedgerConfig

# ⬇️ import the generated Click command object itself
from .compose import app as compose_app
from .compose import write_cmd
from .ledger import app as ledger_app
from .rippled_cfg import app as rippled_app

app = typer.Typer(help="generate_ledger CLI", no_args_is_help=False)

@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    output_file: Path | None = typer.Option(None, "--output-file", "-o"),
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

# keep the explicit sub-apps
app.add_typer(compose_app, name="compose")
app.add_typer(rippled_app, name="rippled")
app.add_typer(ledger_app, name="ledger")
