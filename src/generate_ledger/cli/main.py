from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace
import click
from typer.main import get_command

from generate_ledger.config import ComposeConfig, LedgerConfig
from generate_ledger.cli_defaults import (
    defaults_leaf_from_cfg,
    nest_default_map,
    merge_default_maps,
)
from .compose_click import compose, write_cmd    # generated Click group + command
from . import app as typer_root_app              # your Typer root (for other features)
from .ledger import app as ledger_typer_app      # ledger generation commands

@click.group(invoke_without_command=True, no_args_is_help=False)
@click.option("-o", "--output-file", type=click.Path(path_type=Path), default=None)
@click.pass_context
def cli(ctx: click.Context, output_file: Path | None):
    # init state once
    if ctx.obj is None:
        state = SimpleNamespace(
            compose=ComposeConfig(),
            ledger=LedgerConfig(),
        )
        ctx.obj = state
        # defaults (single source of truth)
        compose_leaf = defaults_leaf_from_cfg(state.compose, "compose-write")
        ctx.default_map = merge_default_maps(
            nest_default_map(("compose","write"), compose_leaf),
        )

    # default action: run `compose write`
    if ctx.invoked_subcommand is None:
        kwargs = {}
        if output_file is not None:
            kwargs["output_file"] = output_file
        return ctx.invoke(write_cmd, **kwargs)

# mount the generated Click "compose" group
cli.add_command(compose, name="compose")

# mount the ledger group directly at root level
cli.add_command(get_command(ledger_typer_app), name="ledger")

# mount your Typer app (converted to Click) under its own namespace if you have others
cli.add_command(get_command(typer_root_app), name="typer")  # optional; or mount specific sub-apps
