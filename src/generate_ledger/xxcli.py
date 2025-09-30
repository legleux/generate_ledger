import click
from types import SimpleNamespace
from gl.config import ComposeConfig, LedgerConfig
from gl.cli_defaults import build_default_map
from gl.commands import _register as _register_commands

@click.group(help="generate_ledger CLI")
@click.pass_context
def cli(ctx: click.Context):
    state = SimpleNamespace(
        compose=ComposeConfig(),
        ledger=LedgerConfig(),
    )
    ctx.obj = state
    # Merge both commands' defaults into one default_map
    dm = {}
    for part in (
        build_default_map(state.compose, "compose-write"),
        build_default_map(state.ledger, "ledger-write"),
    ):
        dm.update(part)
    ctx.default_map = dm

_register_commands(cli)

if __name__ == "__main__":
    cli()
