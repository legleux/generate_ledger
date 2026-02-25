# src/generate_ledger/commands/compose_writer.py
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import click

# Library writer (your implementation that actually writes the file)
from gl.compose import write_compose_file


def _do_compose_write(
    state: SimpleNamespace,
    output_file: Path | None,
    validators: int | None,
    validator_image: str | None,
    validator_name: str | None,
    validator_version: str | None,
    hubs: int | None,
) -> None:
    """Apply CLI overrides to the ComposeConfig and write the compose file."""
    cfg = state.compose  # provided by ctx.obj in the root CLI

    # Build an updated config with only the values the user provided
    update: dict[str, object] = {}
    if validators is not None:
        update["num_validators"] = validators
    if validator_image is not None:
        update["validator_image"] = validator_image
    if validator_name is not None:
        update["validator_name"] = validator_name
    if validator_version is not None:
        update["validator_version"] = validator_version
    if hubs is not None:
        update["num_hubs"] = hubs

    cfg_over = cfg.model_copy(update=update) if update else cfg  # pydantic v2

    path = write_compose_file(output_file=output_file, config=cfg_over)
    click.echo(f"Wrote {path}")


# --- Single-level command -----------------------------------------------------

@click.command("compose-write")
@click.option("-o", "--output-file", type=click.Path(path_type=Path), show_default=True)
@click.option("-v", "--validators", type=int, show_default=True)
@click.option("--validator-image", type=str, show_default=True)
@click.option("--validator-name", type=str, show_default=True)
@click.option("--validator-version", type=str, show_default=True)
@click.option("--hubs", type=int, show_default=True)
@click.pass_obj
def compose_write(
    state: SimpleNamespace,
    output_file: Path | None,
    validators: int | None,
    validator_image: str | None,
    validator_name: str | None,
    validator_version: str | None,
    hubs: int | None,
) -> None:
    """Write the docker-compose file using config-driven defaults."""
    _do_compose_write(
        state, output_file, validators, validator_image, validator_name, validator_version, hubs
    )


# --- Nested alias: `compose gen` ---------------------------------------------

@click.group("compose", help="Compose-related commands.")
def compose_group() -> None:
    """Group for compose-related subcommands."""
    # No-op; subcommands attach below.

@compose_group.command("gen")
@click.option("-o", "--output-file", type=click.Path(path_type=Path), show_default=True)
@click.option("-v", "--validators", type=int, show_default=True)
@click.option("--validator-image", type=str, show_default=True)
@click.option("--validator-name", type=str, show_default=True)
@click.option("--validator-version", type=str, show_default=True)
@click.option("--hubs", type=int, show_default=True)
@click.pass_obj
def compose_gen(
    state: SimpleNamespace,
    output_file: Path | None,
    validators: int | None,
    validator_image: str | None,
    validator_name: str | None,
    validator_version: str | None,
    hubs: int | None,
) -> None:
    """Generate docker-compose from config (alias of compose-write)."""
    _do_compose_write(
        state, output_file, validators, validator_image, validator_name, validator_version, hubs
    )
