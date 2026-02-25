from pathlib import Path
from types import SimpleNamespace

import click

from gl.ledger import write_ledger_file


@click.command("ledger-write")
@click.option("--output-file", type=click.Path(path_type=Path), show_default=True)
@click.option("--accounts", type=int, show_default=True)
@click.pass_obj
def ledger_write(
    state: SimpleNamespace,   # ⬅ receives the namespace
    output_file: Path | None,
    accounts: int,
):
    cfg = state.ledger         # ⬅ pull the LedgerConfig out
    cfg_over = cfg.model_copy(update={
        "num_accounts": accounts,
    })
    path = write_ledger_file(output_file=output_file, config=cfg_over)
    click.echo(f"Wrote {path}")
