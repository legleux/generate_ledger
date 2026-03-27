"""CLI command for docker-compose.yml generation."""

from pathlib import Path

import typer

app = typer.Typer(help="Generate a docker-compose.yml for an XRPL test network.")


@app.callback(invoke_without_command=True)
def compose(
    base_dir: Path = typer.Option(
        Path("testnet"),
        "--base-dir",
        "-b",
        help="Root output directory (must contain a volumes/ subdirectory from `gen xrpld`).",
    ),
    ledger_file: Path | None = typer.Option(
        None,
        "--ledger-file",
        "-l",
        help="Path to ledger.json. If provided, mounts it into validator containers.",
    ),
    validators: int = typer.Option(5, "--validators", "-v", min=1, help="Number of validator nodes."),
    image: str = typer.Option("rippleci/xrpld:develop", "--image", help="Docker image for xrpld nodes."),
):
    """Generate a docker-compose.yml from existing xrpld configs.

    Requires that `gen xrpld` has already been run to create the volumes/ directory.

    Examples:

        # After running gen ledger and gen xrpld:
        gen compose -b ./testnet --validators 5 -l ./testnet/ledger.json

        # Without a ledger file:
        gen compose -b ./testnet --validators 3
    """
    from generate_ledger.compose import ComposeConfig, write_compose_file  # noqa: PLC0415

    volumes_dir = base_dir / "volumes"
    if not volumes_dir.is_dir():
        typer.secho(
            f"ERROR: {volumes_dir} does not exist. Run `gen xrpld` first to generate validator configs.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    mount_ledger = False
    if ledger_file is not None:
        if not ledger_file.is_file():
            typer.secho(
                f"ERROR: ledger file not found: {ledger_file}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)
        mount_ledger = True

    if ":" in image:
        img_name, img_tag = image.rsplit(":", 1)
    else:
        img_name, img_tag = image, "latest"

    compose_cfg = ComposeConfig(
        num_validators=validators,
        base_dir=base_dir,
        validator_image=img_name,
        validator_image_tag=img_tag,
        hub_image=img_name,
        hub_image_tag=img_tag,
        mount_ledger=mount_ledger,
    )

    compose_path = write_compose_file(config=compose_cfg)
    typer.echo(f"Generated {compose_path}")
