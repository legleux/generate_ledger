from pathlib import Path
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
