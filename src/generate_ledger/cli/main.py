"""Root CLI — ``gen`` generates a complete XRPL testnet by default.

Subcommands (``gen ledger``, ``gen xrpld``) run individual pipeline steps.
"""

from __future__ import annotations

from pathlib import Path

import typer
from typer.main import get_command

from .ledger import app as ledger_app
from .xrpld_cfg import app as xrpld_app

app = typer.Typer(
    invoke_without_command=True,
    no_args_is_help=False,
    help="Generate custom XRPL genesis ledgers and test network environments.",
)
app.add_typer(ledger_app, name="ledger")
app.add_typer(xrpld_app, name="xrpld")


def _print_ledgend() -> None:
    import zlib  # noqa: PLC0415
    from importlib.resources import files  # noqa: PLC0415

    data = files("generate_ledger.data").joinpath("ledgend.bin").read_bytes()
    typer.echo(zlib.decompress(data).decode("utf-8"))


@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    output_dir: Path = typer.Option(Path("testnet"), "--output-dir", "-o", help="Root output directory."),
    validators: int = typer.Option(5, "--validators", "-v", min=1, help="Number of validator nodes."),
    num_accounts: int = typer.Option(1000, "--accounts", help="Number of regular (non-gateway) accounts."),
    balance: str = typer.Option(str(100_000_000_000), "--balance", "-b", help="Default account balance in drops."),
    gpu: bool = typer.Option(False, "--gpu", help="GPU-accelerated account generation."),
    trustline: list[str] | None = typer.Option(
        None, "--trustline", "-t", help="Trustline: 'acct1:acct2:currency:limit'. Repeatable."
    ),
    gateways: int = typer.Option(4, "--gateways", help="Number of gateway accounts. 0 = disabled."),
    assets_per_gateway: int = typer.Option(4, "--assets-per-gateway", help="Assets per gateway."),
    gateway_currencies: str = typer.Option("USD,CNY,BTC,ETH", "--gateway-currencies", help="Currency pool."),
    gateway_coverage: float = typer.Option(1.0, "--gateway-coverage", help="Fraction of accounts with trustlines."),
    gateway_connectivity: float = typer.Option(1.0, "--gateway-connectivity", help="Fraction of gateways connected."),
    gateway_seed: int | None = typer.Option(None, "--gateway-seed", help="RNG seed for reproducibility."),
    amm_pool: list[str] | None = typer.Option(
        None, "--amm-pool", "-a", help="AMM pool: 'asset1:asset2:amt1:amt2[:fee[:creator]]'."
    ),
    amendment_profile: str = typer.Option("release", "--amendment-profile", help="release, develop, or custom."),
    amendment_source: str | None = typer.Option(None, "--amendment-source", help="Path to features.macro or JSON."),
    peer_port: int = typer.Option(51235, "--peer-port", help="Peer port for [ips_fixed]."),
    amendment_majority_time: str | None = typer.Option(None, "--amendment-majority-time"),
    base_fee: int = typer.Option(121, "--base-fee", help="Base fee (drops)."),
    reserve_base: int = typer.Option(2_000_000, "--reserve-base", help="Reserve base (drops)."),
    reserve_inc: int = typer.Option(666, "--reserve-inc", help="Reserve increment (drops)."),
    image: str = typer.Option("rippleci/xrpld:develop", "--image", help="Docker image for xrpld nodes."),
    log_level: str = typer.Option("info", "--log-level", help="Log level (trace/debug/info/warning/error/fatal)"),
    ledgend: bool = typer.Option(False, "--ledgend", hidden=True, help="Show the ledgen(d) logo."),
):
    """Generate a complete XRPL testnet: ledger.json, xrpld configs, and docker-compose.yml."""
    if ledgend:
        _print_ledgend()
        raise typer.Exit()

    if ctx.invoked_subcommand is not None:
        return

    from generate_ledger.cli.shared_options import (  # noqa: PLC0415
        build_ledger_config,
        parse_amm_pool_specs,
        parse_trustline_specs,
        run_full_pipeline,
    )

    if amendment_source:
        amendment_profile = "custom" if amendment_source.endswith(".json") else "develop"

    explicit_trustlines = parse_trustline_specs(trustline)
    amm_pools = parse_amm_pool_specs(amm_pool)

    ledger_config = build_ledger_config(
        base_dir=output_dir,
        num_accounts=num_accounts,
        gateways=gateways,
        balance=balance,
        gpu=gpu,
        gateway_currencies=gateway_currencies,
        assets_per_gateway=assets_per_gateway,
        gateway_coverage=gateway_coverage,
        gateway_connectivity=gateway_connectivity,
        gateway_seed=gateway_seed,
        explicit_trustlines=explicit_trustlines,
        amm_pools=amm_pools,
        amendment_profile=amendment_profile,
        amendment_source=amendment_source,
        base_fee=base_fee,
        reserve_base=reserve_base,
        reserve_inc=reserve_inc,
    )

    run_full_pipeline(
        output_dir=output_dir,
        ledger_config=ledger_config,
        amendment_profile=amendment_profile,
        amendment_source=amendment_source,
        validators=validators,
        peer_port=peer_port,
        amendment_majority_time=amendment_majority_time,
        base_fee=base_fee,
        reserve_base=reserve_base,
        reserve_inc=reserve_inc,
        image=image,
        log_level=log_level,
    )


# Click-compatible entry point for pyproject.toml
cli = get_command(app)
