"""Unified ``gen auto`` command — generates ledger, rippled configs, and docker-compose in one step."""

from pathlib import Path

import typer

app = typer.Typer(help="Generate a complete testnet (ledger + rippled configs + docker-compose).")


@app.command()
def auto(
    # Output
    output_dir: Path = typer.Option(
        Path("testnet"), "--output-dir", "-o",
        help="Root output directory for all generated files.",
    ),
    # Topology
    validators: int = typer.Option(
        5, "--validators", "-v", min=1, help="Number of validator nodes.",
    ),
    # Ledger: accounts
    num_accounts: int = typer.Option(
        40, "--accounts", "-n",
        help="Number of regular (non-gateway) accounts. Total = accounts + gateways.",
    ),
    balance: str = typer.Option(
        str(100_000_000_000), "--balance", "-b",
        help="Default account balance in drops.",
    ),
    algo: str = typer.Option(
        "ed25519", "--algo",
        help="Key algorithm: ed25519 (fast, default) or secp256k1.",
    ),
    # Ledger: trustlines
    trustline: list[str] | None = typer.Option(
        None, "--trustline", "-t",
        help="Explicit trustline spec: 'acct1:acct2:currency:limit'. Repeatable.",
    ),
    # Ledger: gateway topology
    gateways: int = typer.Option(
        0, "--gateways",
        help="Number of gateway accounts (first N accounts become gateways). 0 = disabled.",
    ),
    assets_per_gateway: int = typer.Option(
        4, "--assets-per-gateway",
        help="Number of unique assets each gateway issues.",
    ),
    gateway_currencies: str = typer.Option(
        "USD,EUR,GBP,JPY,BTC,ETH,CNY,MXN,CAD,AUD,CHF,KRW,SGD,HKD,NOK,SEK",
        "--gateway-currencies",
        help="Comma-separated currency pool for gateway assets (distributed round-robin).",
    ),
    gateway_coverage: float = typer.Option(
        0.5, "--gateway-coverage",
        help="Fraction of non-gateway accounts that receive trustlines (0.0-1.0).",
    ),
    gateway_connectivity: float = typer.Option(
        0.5, "--gateway-connectivity",
        help="Fraction of gateways each trustline-holding account connects to (0.0-1.0).",
    ),
    gateway_seed: int | None = typer.Option(
        None, "--gateway-seed",
        help="RNG seed for reproducible gateway topology.",
    ),
    # Ledger: AMM
    amm_pool: list[str] | None = typer.Option(
        None, "--amm-pool", "-a",
        help="AMM pool spec: 'asset1:asset2:amount1:amount2[:fee[:creator]]'. Repeatable.",
    ),
    # Amendments
    amendment_profile: str = typer.Option(
        "release", "--amendment-profile",
        help="Amendment profile: release, develop, or custom.",
    ),
    amendment_source: str | None = typer.Option(
        None, "--amendment-source",
        help="Path to features.macro (develop) or custom JSON file.",
    ),
    # Rippled config
    peer_port: int = typer.Option(
        51235, "--peer-port",
        help="Port used in [ips_fixed] entries.",
    ),
    amendment_majority_time: str | None = typer.Option(
        None, "--amendment-majority-time",
        help="Override amendment majority time (e.g. '2 minutes').",
    ),
    # Fees
    base_fee: int = typer.Option(
        121, "--base-fee",
        help="Base fee (drops).",
    ),
    reserve_base: int = typer.Option(
        2_000_000, "--reserve-base",
        help="Reserve base (drops).",
    ),
    reserve_inc: int = typer.Option(
        666, "--reserve-inc",
        help="Reserve increment (drops).",
    ),
):
    """
    Generate a complete testnet in one command: ledger.json, rippled configs, and docker-compose.yml.

    Examples:

        gen auto -o /tmp/testnet -v 5 -n 10

        gen auto -o /tmp/testnet -v 5 -n 10 -t "0:1:USD:1000000000"

        gen auto --amendment-profile develop --amendment-source /path/to/features.macro
    """
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Step 1: Generate ledger.json + accounts.json ---
    typer.echo("=== Step 1/3: Generating ledger.json ===")

    from gl.accounts import AccountConfig  # noqa: PLC0415
    from gl.cli.parsers import ParseError, parse_amm_pool, parse_trustline  # noqa: PLC0415
    from gl.ledger import (  # noqa: PLC0415
        AMMPoolConfig,
        ExplicitTrustline,
        FeeConfig,
        LedgerConfig,
        write_ledger_file,
    )

    # Parse trustline specs
    explicit_trustlines = []
    if trustline:
        for spec in trustline:
            try:
                parsed = parse_trustline(spec)
                explicit_trustlines.append(ExplicitTrustline(
                    account1=parsed.account1,
                    account2=parsed.account2,
                    currency=parsed.currency,
                    limit=parsed.limit,
                ))
            except ParseError as e:
                raise typer.BadParameter(str(e)) from e

    # Parse AMM pool specs
    amm_pools = []
    if amm_pool:
        for spec in amm_pool:
            try:
                parsed = parse_amm_pool(spec)
                amm_pools.append(AMMPoolConfig(
                    asset1_currency=parsed.asset1.currency,
                    asset1_issuer=parsed.asset1.issuer,
                    asset1_amount=parsed.amount1,
                    asset2_currency=parsed.asset2.currency,
                    asset2_issuer=parsed.asset2.issuer,
                    asset2_amount=parsed.amount2,
                    trading_fee=parsed.fee,
                    creator=parsed.creator,
                ))
            except ParseError as e:
                raise typer.BadParameter(str(e)) from e

    from gl.gateways import GatewayConfig  # noqa: PLC0415
    gateway_currency_list = [c.strip().upper() for c in gateway_currencies.split(",") if c.strip()]

    ledger_config = LedgerConfig(
        account_cfg=AccountConfig(num_accounts=num_accounts + gateways, balance=balance, algo=algo),
        fee_cfg=FeeConfig(
            base_fee_drops=base_fee,
            reserve_base_drops=reserve_base,
            reserve_increment_drops=reserve_inc,
        ),
        explicit_trustlines=explicit_trustlines,
        gateway_cfg=GatewayConfig(
            num_gateways=gateways,
            assets_per_gateway=assets_per_gateway,
            currencies=gateway_currency_list,
            coverage=gateway_coverage,
            connectivity=gateway_connectivity,
            seed=gateway_seed,
        ),
        amm_pools=amm_pools,
        base_dir=output_dir,
        amendment_profile=amendment_profile,
        amendment_profile_source=amendment_source,
    )

    write_ledger_file(config=ledger_config)
    typer.echo(f"  ledger.json  -> {output_dir / 'ledger.json'}")
    typer.echo(f"  accounts.json -> {output_dir / 'accounts.json'}")

    # --- Step 2: Generate rippled configs ---
    typer.echo("=== Step 2/3: Generating rippled configs ===")

    from generate_ledger.rippled_cfg import RippledConfigSpec  # noqa: PLC0415
    from gl.amendments import get_amendments_for_profile  # noqa: PLC0415

    # Get amendment names from the same profile used for ledger generation
    amendments = get_amendments_for_profile(
        profile=amendment_profile,
        source=amendment_source,
    )
    feature_names = [a.name for a in amendments if a.enabled]

    volumes_dir = output_dir / "volumes"
    spec = RippledConfigSpec(
        num_validators=validators,
        base_dir=volumes_dir,
        peer_port=peer_port,
        features=feature_names,
        amendment_majority_time=amendment_majority_time,
        reference_fee=base_fee,
        account_reserve=reserve_base,
        owner_reserve=reserve_inc,
    )
    result = spec.write()
    for p in result.paths:
        typer.echo(f"  {p}")

    # --- Step 3: Generate docker-compose.yml ---
    typer.echo("=== Step 3/3: Generating docker-compose.yml ===")

    from generate_ledger.compose import write_compose_file  # noqa: PLC0415
    from generate_ledger.config import ComposeConfig  # noqa: PLC0415

    compose_cfg = ComposeConfig(
        num_validators=validators,
        base_dir=output_dir,
    )
    compose_path = write_compose_file(config=compose_cfg)
    typer.echo(f"  {compose_path}")

    typer.echo(f"\nDone! Testnet files written to {output_dir}")
