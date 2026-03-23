from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import click
from typer.main import get_command

from generate_ledger.cli_defaults import (
    defaults_leaf_from_cfg,
    merge_default_maps,
    nest_default_map,
)
from generate_ledger.config import ComposeConfig, LedgerConfig

from .auto_cmd import app as auto_typer_app
from .compose_click import compose, write_cmd  # generated Click group + command
from .ledger import app as ledger_typer_app  # ledger generation commands
from .rippled_cfg import app as rippled_typer_app


def _print_ledgend() -> None:
    import zlib  # noqa: PLC0415
    from importlib.resources import files  # noqa: PLC0415

    data = files("generate_ledger.data").joinpath("ledgend.bin").read_bytes()
    click.echo(zlib.decompress(data).decode("utf-8"))


@click.group(invoke_without_command=True, no_args_is_help=False)
@click.option("-o", "--output-file", type=click.Path(path_type=Path), default=None)
@click.option("--ledgend", is_flag=True, hidden=True, help="Show the ledgen(d) logo.")
@click.pass_context
def cli(ctx: click.Context, output_file: Path | None, ledgend: bool):
    if ledgend:
        _print_ledgend()
        ctx.exit(0)
        return

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
            nest_default_map(("compose", "write"), compose_leaf),
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

# mount rippled config generation
cli.add_command(get_command(rippled_typer_app), name="rippled")

# mount unified auto command
cli.add_command(get_command(auto_typer_app), name="auto")
