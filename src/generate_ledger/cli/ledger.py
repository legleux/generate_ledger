import typer
from pathlib import Path

from gl.accounts import generate_accounts, write_accounts_json
from gl.amendments import fetch_amendments
from gl.ledger_build import (
    assemble_ledger_json,
    write_ledger_json,
    FeeSettings,
)
from gl.models.namespace import ACCOUNT


app = typer.Typer(help="Commands to generate custom ledger.json files.")


@app.command()
def ledger(
    num_accounts: int = typer.Option(40, "--num-accounts", "-n", help="Number of accounts to generate."),
    outdir: Path = typer.Option(Path("testnet"), "--outdir", "-o", help="Output directory."),
    rpc_url: str = typer.Option("https://s.devnet.rippletest.net:51234", "--rpc", help="RPC server to fetch amendments."),
    include_amendments: bool = typer.Option(True, "--amendments/--no-amendments", help="Include enabled amendments."),
    base_fee: int = typer.Option(121, help="Base fee (drops)."),
    reserve_base: int = typer.Option(2_000_000, help="Reserve base (drops)."),
    reserve_inc: int = typer.Option(123_456, help="Reserve increment (drops)."),
):
    """
    Build a ledger.json with generated accounts, fees, and optional amendments.
    """
    outdir.mkdir(parents=True, exist_ok=True)

    # 1. accounts
    accounts = generate_accounts(num_accounts)
    accounts_file = outdir / "accounts.json"
    write_accounts_json(accounts, accounts_file)

    # 2. fees
    fees = FeeSettings(base_fee_drops=base_fee, reserve_base_drops=reserve_base, reserve_increment_drops=reserve_inc)

    # 3. amendments
    amendments = fetch_amendments(rpc_url) if include_amendments else []

    # 4. ledger assembly
    ledger = assemble_ledger_json(
        accounts=accounts,
        account_ns=ACCOUNT,
        fees=fees,
        amendments=amendments,
    )
    ledger_file = outdir / "ledger.json"
    write_ledger_json(ledger, ledger_file)

    typer.echo(f"Wrote {accounts_file.resolve()} and {ledger_file.resolve()}")
