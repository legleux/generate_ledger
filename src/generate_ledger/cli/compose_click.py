# src/generate_ledger/cli/compose_click.py
from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from generate_ledger.compose import write_compose_file
from generate_ledger.config import ComposeConfig

from .click_builder import build_command_from_defaults


def _runner(base_cfg: ComposeConfig, overrides: dict[str, Any], output_file: Path | str | None):
    cfg = base_cfg.model_copy(update=overrides) if overrides else base_cfg
    result = write_compose_file(output_file=output_file, config=cfg)
    click.echo(f"Wrote {result.resolve()}")


# Define the group via decorator so the function *is* the group's callback.
@click.group(name="compose", help="Docker Compose helpers.", invoke_without_command=True)
@click.pass_context
def compose(ctx: click.Context):
    # If the user ran `gl compose` with no subcommand, dispatch to the default.
    if ctx.invoked_subcommand is None:
        # write_cmd is defined below; it's available by the time this runs.
        return ctx.invoke(write_cmd)


# Generate the command from CLI_DEFAULTS and attach it to the group.
write_cmd = build_command_from_defaults(
    command_name="write",
    command_key="compose-write",  # key in CLI_DEFAULTS
    model_cls=ComposeConfig,
    state_attr="compose",
    runner=_runner,
)
compose.add_command(write_cmd)
