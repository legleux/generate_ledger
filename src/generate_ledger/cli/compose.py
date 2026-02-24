from pathlib import Path
from typing import Optional
import click
import typer
from typer.main import get_command

from generate_ledger.config import ComposeConfig
from generate_ledger.compose import write_compose_file
from .auto import build_command_from_defaults

app = typer.Typer(help="Docker Compose helpers.")

@app.callback()
def _compose_root(ctx: typer.Context):
    """Group entrypoint; needed so get_command(app) can build a Click group."""
    pass

def _runner(base_cfg: ComposeConfig, overrides: dict, output_file: Path | None):
    cfg = base_cfg.model_copy(update=overrides) if overrides else base_cfg
    write_compose_file(output_file=output_file, config=cfg)
    click.echo(f"Wrote {output_file.resolve() if output_file else 'compose file (default path)'}")

write_cmd = build_command_from_defaults(
    command_name="write",
    command_key="compose-write",
    model_cls=ComposeConfig,
    state_attr="compose",
    runner=_runner,
)

# After the callback is defined, this now works:
get_command(app).add_command(write_cmd)

# Also add a Typer command wrapper for when this app is nested in another Typer app
@app.command("write")
def write_typer(
    ctx: typer.Context,
    output_file: Optional[Path] = typer.Option(None, "-o", "--output-file"),
    validators: Optional[int] = typer.Option(None, "--validators"),
    base_dir: Optional[Path] = typer.Option(None, "--base-dir"),
):
    """
    Generate docker-compose.yml for XRPL validator network.
    """
    # Get config from context
    if ctx.obj is None:
        from types import SimpleNamespace
        from generate_ledger.config import LedgerConfig
        ctx.obj = SimpleNamespace(compose=ComposeConfig(), ledger=LedgerConfig())

    base_cfg = ctx.obj.compose

    # Build overrides
    overrides = {}
    if validators is not None:
        overrides["num_validators"] = validators
    if base_dir is not None:
        overrides["base_dir"] = base_dir

    _runner(base_cfg, overrides, output_file)
