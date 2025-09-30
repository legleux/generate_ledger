# src/my_app/commands/config.py
import click
from gl.services import config_service
from gl.utils import editor

@click.group(name="config")
def config_group():
    """Config operations."""

@config_group.command("path")
@click.pass_obj
def path_cmd(ctx):
    click.echo(config_service.resolve_config_path(ctx["config_path"]))

@config_group.command("init")
@click.option("--force", is_flag=True)
@click.pass_obj
def init_cmd(ctx, force: bool):
    p = config_service.init_config(ctx["config_path"], force=force)
    click.echo(f"Initialized {p}")

@config_group.command("edit")
@click.pass_obj
def edit_cmd(ctx):
    p = config_service.ensure_config(ctx["config_path"])
    editor.open_in_editor(p)

@config_group.command("show")
@click.option("--raw", is_flag=True)
@click.pass_obj
def show_cmd(ctx, raw: bool):
    cfg = config_service.load_effective_config(
        profile=ctx["profile"],
        config_path=ctx["config_path"],
        cli_sets=ctx["sets"],
    )
    click.echo(config_service.format_config(cfg, redact=not raw))

@config_group.command("validate")
@click.pass_obj
def validate_cmd(ctx):
    config_service.validate(
        profile=ctx["profile"],
        config_path=ctx["config_path"],
        cli_sets=ctx["sets"],
    )
    click.echo("OK")
