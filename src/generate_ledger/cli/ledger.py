"""CLI command for ledger generation with trustlines and AMM pools."""
from pathlib import Path

import typer

from gl.accounts import AccountConfig
from gl.cli.parsers import ParseError, parse_amm_pool, parse_trustline
from gl.ledger import AMMPoolConfig, ExplicitTrustline, LedgerConfig, write_ledger_file
from gl.trustlines import TrustlineConfig

app = typer.Typer(help="Commands to generate custom ledger.json files.")


def _build_amm_pool_config(spec) -> AMMPoolConfig:
    """Convert a ParsedAMMPool to AMMPoolConfig."""
    return AMMPoolConfig(
        asset1_currency=spec.asset1.currency,
        asset1_issuer=spec.asset1.issuer,
        asset1_amount=spec.amount1,
        asset2_currency=spec.asset2.currency,
        asset2_issuer=spec.asset2.issuer,
        asset2_amount=spec.amount2,
        trading_fee=spec.fee,
        creator=spec.creator,
    )


@app.command()
def ledger(
    # Account options
    num_accounts: int = typer.Option(
        40, "--num-accounts", "-n",
        help="Number of accounts to generate."
    ),
    balance: str = typer.Option(
        str(100_000_000000), "--balance", "-b",
        help="Default account balance in drops (default: 100k XRP)."
    ),
    algo: str = typer.Option(
        "ed25519", "--algo",
        help="Key algorithm: ed25519 (fast, default) or secp256k1."
    ),

    # Output options
    outdir: Path = typer.Option(
        Path("testnet"), "--outdir", "-o",
        help="Output directory."
    ),

    # Trustline options
    num_trustlines: int = typer.Option(
        0, "--num-trustlines",
        help="Number of random trustlines to generate."
    ),
    trustline: list[str] | None = typer.Option(
        None, "--trustline", "-t",
        help="Explicit trustline spec: 'account1:account2:currency:limit'. Repeatable."
    ),
    currencies: str = typer.Option(
        "USD,EUR,GBP", "--currencies",
        help="Comma-separated currencies for random trustlines."
    ),
    trustline_limit: int = typer.Option(
        100_000_000_000, "--trustline-limit",
        help="Default trust limit for random trustlines."
    ),

    # AMM options
    amm_pool: list[str] | None = typer.Option(
        None, "--amm-pool", "-a",
        help="AMM pool spec: 'asset1:asset2:amount1:amount2[:fee[:creator]]'. Repeatable."
    ),

    # Amendment options
    amendment_profile: str | None = typer.Option(
        None, "--amendment-profile",
        help="Amendment profile: release, develop, or custom."
    ),
    amendment_source: str | None = typer.Option(
        None, "--amendment-source",
        help="Path to features.macro (develop) or JSON file (custom)."
    ),
    enable_amendment: list[str] | None = typer.Option(
        None, "--enable-amendment",
        help="Force-enable a specific amendment by name. Repeatable."
    ),
    disable_amendment: list[str] | None = typer.Option(
        None, "--disable-amendment",
        help="Force-disable a specific amendment by name. Repeatable."
    ),

    # Fee options
    base_fee: int = typer.Option(
        121, "--base-fee",
        help="Base fee (drops)."
    ),
    reserve_base: int = typer.Option(
        2_000_000, "--reserve-base",
        help="Reserve base (drops)."
    ),
    reserve_inc: int = typer.Option(
        666, "--reserve-inc",
        help="Reserve increment (drops)."
    ),
):
    """
    Build a ledger.json with accounts, trustlines, and AMM pools.

    Examples:

        # Basic: 10 accounts
        gen ledger -n 10

        # With 5 random trustlines
        gen ledger -n 10 --num-trustlines 5 --currencies USD,EUR

        # With explicit trustlines (account indices)
        gen ledger -n 5 -t "0:1:USD:1000000000" -t "1:2:EUR:500000000"

        # With AMM pool (XRP/USD, account[0] as issuer)
        gen ledger -n 5 -a "XRP:USD:0:1000000000000:1000000"

        # Combined
        gen ledger -n 10 --num-trustlines 3 -t "0:1:USD:1000000000" -a "XRP:USD:0:1000000000000:1000000:500:1"
    """
    outdir.mkdir(parents=True, exist_ok=True)

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
                amm_pools.append(_build_amm_pool_config(parsed))
            except ParseError as e:
                raise typer.BadParameter(str(e)) from e

    # Parse currencies
    currency_list = [c.strip().upper() for c in currencies.split(",") if c.strip()]

    # Build config
    from gl.ledger import FeeConfig  # noqa: PLC0415
    config_kwargs: dict = dict(
        account_cfg=AccountConfig(
            num_accounts=num_accounts,
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
        amm_pools=amm_pools,
        base_dir=outdir,
    )
    if amendment_profile is not None:
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
    typer.echo(f"Generated ledger.json at {output_file}")
    typer.echo(f"  Accounts: {num_accounts}")
    if num_trustlines > 0:
        typer.echo(f"  Random trustlines: {num_trustlines}")
    if explicit_trustlines:
        typer.echo(f"  Explicit trustlines: {len(explicit_trustlines)}")
    if amm_pools:
        typer.echo(f"  AMM pools: {len(amm_pools)}")
