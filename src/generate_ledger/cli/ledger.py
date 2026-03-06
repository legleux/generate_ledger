"""CLI command for ledger generation with trustlines and AMM pools."""

from pathlib import Path

import typer

from generate_ledger.accounts import AccountConfig
from generate_ledger.cli.parsers import (
    ParseError,
    build_amm_pool_config,
    parse_amm_pool,
    parse_mpt_spec,
    parse_trustline,
)
from generate_ledger.ledger import ExplicitTrustline, LedgerConfig, MPTIssuanceConfig, write_ledger_file
from generate_ledger.trustlines import TrustlineConfig

app = typer.Typer(help="Commands to generate custom ledger.json files.")


@app.command()
def ledger(
    # Account options
    num_accounts: int = typer.Option(
        40, "--accounts", help="Number of regular (non-gateway) accounts. Total = accounts + gateways."
    ),
    balance: str = typer.Option(
        str(100_000_000000), "--balance", "-b", help="Default account balance in drops (default: 100k XRP)."
    ),
    algo: str = typer.Option("ed25519", "--algo", help="Key algorithm: ed25519 (fast, default) or secp256k1."),
    # Output options
    outdir: Path = typer.Option(Path("testnet"), "--output-dir", "-o", help="Output directory."),
    # Trustline options
    num_trustlines: int = typer.Option(0, "--num-trustlines", help="Number of random trustlines to generate."),
    trustline: list[str] | None = typer.Option(
        None, "--trustline", "-t", help="Explicit trustline spec: 'account1:account2:currency:limit'. Repeatable."
    ),
    currencies: str = typer.Option(
        "USD,EUR,GBP", "--currencies", help="Comma-separated currencies for random trustlines."
    ),
    trustline_limit: int = typer.Option(
        100_000_000_000, "--trustline-limit", help="Default trust limit for random trustlines."
    ),
    # Gateway topology options
    gateways: int = typer.Option(
        0,
        "--gateways",
        help="Number of gateway accounts (first N accounts become gateways). 0 = disabled.",
    ),
    assets_per_gateway: int = typer.Option(
        4,
        "--assets-per-gateway",
        help="Number of unique assets each gateway issues.",
    ),
    gateway_currencies: str = typer.Option(
        "USD,EUR,GBP,JPY,BTC,ETH,CNY,MXN,CAD,AUD,CHF,KRW,SGD,HKD,NOK,SEK",
        "--gateway-currencies",
        help="Comma-separated currency pool for gateway assets (distributed round-robin).",
    ),
    gateway_coverage: float = typer.Option(
        0.5,
        "--gateway-coverage",
        help="Fraction of non-gateway accounts that receive trustlines (0.0-1.0).",
    ),
    gateway_connectivity: float = typer.Option(
        0.5,
        "--gateway-connectivity",
        help="Fraction of gateways each trustline-holding account connects to (0.0-1.0).",
    ),
    gateway_seed: int | None = typer.Option(
        None,
        "--gateway-seed",
        help="RNG seed for reproducible gateway topology.",
    ),
    # AMM options
    amm_pool: list[str] | None = typer.Option(
        None, "--amm-pool", "-a", help="AMM pool spec: 'asset1:asset2:amount1:amount2[:fee[:creator]]'. Repeatable."
    ),
    # MPT options
    mpt: list[str] | None = typer.Option(
        None,
        "--mpt",
        help=(
            "MPT issuance spec: 'issuer:sequence[:max_amount[:flags[:scale[:fee[:metadata]]]]]'."
            " Requires MPTokensV1 amendment. Repeatable."
        ),
    ),
    # Amendment options
    amendment_profile: str = typer.Option(
        "develop",
        "--amendment-profile",
        help="Amendment profile: develop (default, auto-fetches from GitHub), release (curated mainnet), or custom.",
    ),
    amendment_source: str | None = typer.Option(
        None,
        "--amendment-source",
        help="Path to features.macro or JSON file. Overrides GitHub fetch. Can also set GL_FEATURES_MACRO env var.",
    ),
    enable_amendment: list[str] | None = typer.Option(
        None, "--enable-amendment", help="Force-enable a specific amendment by name. Repeatable."
    ),
    disable_amendment: list[str] | None = typer.Option(
        None, "--disable-amendment", help="Force-disable a specific amendment by name. Repeatable."
    ),
    # Fee options
    base_fee: int = typer.Option(121, "--base-fee", help="Base fee (drops)."),
    reserve_base: int = typer.Option(2_000_000, "--reserve-base", help="Reserve base (drops)."),
    reserve_inc: int = typer.Option(666, "--reserve-inc", help="Reserve increment (drops)."),
):
    """
    Build a ledger.json with accounts, trustlines, and AMM pools.

    Examples:

        # Basic: 10 accounts
        gen ledger --accounts 10

        # With 5 random trustlines
        gen ledger --accounts 10 --num-trustlines 5 --currencies USD,EUR

        # With explicit trustlines (account indices)
        gen ledger --accounts 5 -t "0:1:USD:1000000000" -t "1:2:EUR:500000000"

        # With AMM pool (XRP/USD, account[0] as issuer)
        gen ledger --accounts 5 -a "XRP:USD:0:1000000000000:1000000"

        # Combined
        gen ledger --accounts 10 --num-trustlines 3 -t "0:1:USD:1000000000" -a "XRP:USD:0:1000000000000:1000000:500:1"
    """
    outdir.mkdir(parents=True, exist_ok=True)

    # Parse trustline specs
    explicit_trustlines = []
    if trustline:
        for spec in trustline:
            try:
                parsed = parse_trustline(spec)
                explicit_trustlines.append(
                    ExplicitTrustline(
                        account1=parsed.account1,
                        account2=parsed.account2,
                        currency=parsed.currency,
                        limit=parsed.limit,
                    )
                )
            except ParseError as e:
                raise typer.BadParameter(str(e)) from e

    # Parse AMM pool specs
    amm_pools = []
    if amm_pool:
        for spec in amm_pool:
            try:
                parsed = parse_amm_pool(spec)
                amm_pools.append(build_amm_pool_config(parsed))
            except ParseError as e:
                raise typer.BadParameter(str(e)) from e

    # Parse MPT issuance specs
    mpt_issuances = []
    if mpt:
        for spec in mpt:
            try:
                parsed = parse_mpt_spec(spec)
                mpt_issuances.append(
                    MPTIssuanceConfig(
                        issuer=parsed.issuer,
                        sequence=parsed.sequence,
                        max_amount=parsed.max_amount,
                        flags=parsed.flags,
                        asset_scale=parsed.asset_scale,
                        transfer_fee=parsed.transfer_fee,
                        metadata=parsed.metadata,
                    )
                )
            except ParseError as e:
                raise typer.BadParameter(str(e)) from e

    # Parse currencies
    currency_list = [c.strip().upper() for c in currencies.split(",") if c.strip()]

    # Build config
    from generate_ledger.gateways import GatewayConfig  # noqa: PLC0415
    from generate_ledger.ledger import FeeConfig  # noqa: PLC0415

    gateway_currency_list = [c.strip().upper() for c in gateway_currencies.split(",") if c.strip()]
    config_kwargs: dict = dict(
        account_cfg=AccountConfig(
            num_accounts=num_accounts + gateways,
            balance=balance,
            algo=algo,
        ),
        fee_cfg=FeeConfig(
            base_fee_drops=base_fee,
            reserve_base_drops=reserve_base,
            reserve_increment_drops=reserve_inc,
        ),
        trustlines=TrustlineConfig(
            num_trustlines=num_trustlines,
            currencies=currency_list,
            default_limit=str(trustline_limit),
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
        mpt_issuances=mpt_issuances,
        base_dir=outdir,
    )
    config_kwargs["amendment_profile"] = amendment_profile
    if amendment_source is not None:
        config_kwargs["amendment_profile_source"] = amendment_source
    if enable_amendment:
        config_kwargs["enable_amendments"] = enable_amendment
    if disable_amendment:
        config_kwargs["disable_amendments"] = disable_amendment
    config = LedgerConfig(**config_kwargs)

    # Generate and write ledger
    output_file = write_ledger_file(config=config)

    # Summary
    total_accounts = num_accounts + gateways
    typer.echo(f"Generated ledger.json at {output_file}")
    if gateways > 0:
        typer.echo(f"  Accounts: {total_accounts} ({num_accounts} regular + {gateways} gateways)")
        expected_tl = int(num_accounts * gateway_coverage * gateways * gateway_connectivity * assets_per_gateway)
        typer.echo(f"  Expected gateway trustlines: ~{expected_tl}")
    else:
        typer.echo(f"  Accounts: {total_accounts}")
    if num_trustlines > 0:
        typer.echo(f"  Random trustlines: {num_trustlines}")
    if explicit_trustlines:
        typer.echo(f"  Explicit trustlines: {len(explicit_trustlines)}")
    if amm_pools:
        typer.echo(f"  AMM pools: {len(amm_pools)}")
    if mpt_issuances:
        typer.echo(f"  MPT issuances: {len(mpt_issuances)}")
