from click import Group


def _register(cli: Group) -> None:
    # Import inside to avoid cycles
    from gl.commands.compose_writer import compose_write  # noqa: PLC0415
    from gl.commands.ledger_writer import ledger_write  # noqa: PLC0415
    cli.add_command(compose_write)
    cli.add_command(ledger_write)
