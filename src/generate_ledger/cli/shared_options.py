"""Shared CLI parsing, config-building, and pipeline logic."""

from pathlib import Path

import typer

from generate_ledger.cli.parsers import ParseError, build_amm_pool_config, parse_amm_pool, parse_trustline


def parse_specs(raw_specs: list[str] | None, parser, converter) -> list:
    """Parse a list of CLI spec strings into config objects, raising BadParameter on error."""
    if not raw_specs:
        return []
    result = []
    for spec in raw_specs:
        try:
            result.append(converter(parser(spec)))
        except ParseError as e:
            raise typer.BadParameter(str(e)) from e
    return result


def parse_trustline_specs(raw_specs: list[str] | None):
    """Parse --trustline CLI specs into ExplicitTrustline list."""
    from generate_ledger.ledger import ExplicitTrustline  # noqa: PLC0415

    return parse_specs(
        raw_specs,
        parse_trustline,
        lambda p: ExplicitTrustline(account1=p.account1, account2=p.account2, currency=p.currency, limit=p.limit),
    )


def parse_amm_pool_specs(raw_specs: list[str] | None):
    """Parse --amm-pool CLI specs into AMMPoolConfig list."""
    return parse_specs(raw_specs, parse_amm_pool, build_amm_pool_config)


def build_ledger_config(
    *,
    base_dir: Path,
    num_accounts: int,
    gateways: int,
    balance: str,
    gpu: bool,
    algo: str = "ed25519",
    gateway_currencies: str,
    assets_per_gateway: int,
    gateway_coverage: float,
    gateway_connectivity: float,
    gateway_seed: int | None,
    explicit_trustlines: list,
    amm_pools: list,
    amendment_profile: str,
    amendment_source: str | None = None,
    # ledger-only extras
    num_trustlines: int = 0,
    currencies: str = "USD,EUR,GBP",
    trustline_limit: int = 100_000_000_000,
    enable_amendments: list[str] | None = None,
    disable_amendments: list[str] | None = None,
    mpt_issuances: list | None = None,
    base_fee: int = 121,
    reserve_base: int = 2_000_000,
    reserve_inc: int = 666,
):
    """Build a LedgerConfig from CLI parameters. Shared between ``gen ledger`` and ``gen auto``."""
    from generate_ledger.accounts import AccountConfig  # noqa: PLC0415
    from generate_ledger.gateways import GatewayConfig  # noqa: PLC0415
    from generate_ledger.ledger import FeeConfig, LedgerConfig  # noqa: PLC0415
    from generate_ledger.trustlines import TrustlineConfig  # noqa: PLC0415

    gateway_currency_list = [c.strip().upper() for c in gateway_currencies.split(",") if c.strip()]
    currency_list = [c.strip().upper() for c in currencies.split(",") if c.strip()]

    config_kwargs: dict = dict(
        account_cfg=AccountConfig(
            num_accounts=num_accounts + gateways,
            balance=balance,
            algo=algo,
            use_gpu=gpu,
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
        base_dir=base_dir,
        amendment_profile=amendment_profile,
    )

    if amendment_source is not None:
        config_kwargs["amendment_profile_source"] = amendment_source
    if enable_amendments:
        config_kwargs["enable_amendments"] = enable_amendments
    if disable_amendments:
        config_kwargs["disable_amendments"] = disable_amendments
    if mpt_issuances:
        config_kwargs["mpt_issuances"] = mpt_issuances

    return LedgerConfig(**config_kwargs)


def run_full_pipeline(
    *,
    output_dir: Path,
    ledger_config,
    amendment_profile: str,
    amendment_source: str | None,
    validators: int,
    peer_port: int,
    amendment_majority_time: str | None,
    base_fee: int,
    reserve_base: int,
    reserve_inc: int,
    image: str,
    log_level: str = "info",
):
    """Run the 3-step testnet generation pipeline (ledger + xrpld configs + docker-compose)."""
    from generate_ledger.amendments import get_amendments_for_profile  # noqa: PLC0415
    from generate_ledger.compose import write_compose_file  # noqa: PLC0415
    from generate_ledger.config import ComposeConfig  # noqa: PLC0415
    from generate_ledger.ledger import write_ledger_file  # noqa: PLC0415
    from generate_ledger.xrpld_cfg import XrpldConfigSpec  # noqa: PLC0415

    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: ledger.json + accounts.json
    typer.echo("=== Step 1/3: Generating ledger.json ===")
    write_ledger_file(config=ledger_config)
    typer.echo(f"  ledger.json  -> {output_dir / 'ledger.json'}")
    typer.echo(f"  accounts.json -> {output_dir / 'accounts.json'}")

    # Step 2: xrpld configs
    typer.echo("=== Step 2/3: Generating xrpld configs ===")
    amendments = get_amendments_for_profile(profile=amendment_profile, source=amendment_source)
    feature_names = [a.name for a in amendments if a.enabled]
    spec = XrpldConfigSpec(
        num_validators=validators,
        base_dir=output_dir / "volumes",
        peer_port=peer_port,
        features=feature_names,
        amendment_majority_time=amendment_majority_time,
        reference_fee=base_fee,
        account_reserve=reserve_base,
        owner_reserve=reserve_inc,
        log_level=log_level,
    )
    result = spec.write()
    for p in result.paths:
        typer.echo(f"  {p}")

    # Step 3: docker-compose.yml
    typer.echo("=== Step 3/3: Generating docker-compose.yml ===")
    if ":" in image:
        img_name, img_tag = image.rsplit(":", 1)
    else:
        img_name, img_tag = image, "latest"
    compose_cfg = ComposeConfig(
        num_validators=validators,
        base_dir=output_dir,
        validator_image=img_name,
        validator_image_tag=img_tag,
        hub_image=img_name,
        hub_image_tag=img_tag,
    )
    compose_path = write_compose_file(config=compose_cfg)
    typer.echo(f"  {compose_path}")

    typer.echo(f"\nDone! Testnet files written to {output_dir}")
