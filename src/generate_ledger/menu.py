from pathlib import Path

import typer
from gl.accounts import generate_accounts, write_accounts_json
from gl.amendments import fetch_amendments
from gl.ledger_build import FeeSettings, assemble_ledger_json, write_ledger_json
from gl.models.ledger import LedgerNamespace  # if you switched to constants, import that instead
from InquirerPy import inquirer

app = typer.Typer(help="Arrow-key interactive menu")

@app.command("run")
def run():
    while True:
        choice = inquirer.select(
            message="What do you want to do?",
            choices=[
                ("Ledger → Build", "ledger_build"),
                ("Ledger → Show amendments", "ledger_show"),
                ("Compose → Write", "compose_write"),
                ("Exit", "exit"),
            ],
        ).execute()

        if choice == "ledger_build":
            num_accounts = int(inquirer.number(message="Number of accounts:", default=40).execute())
            outdir = Path(inquirer.text(message="Output directory:", default="testnet").execute())
            rpc_url = inquirer.text(
                message="RPC URL:", default="https://s.devnet.rippletest.net:51234"
            ).execute()
            include_amendments = inquirer.confirm(message="Include amendments?", default=True).execute()
            base_fee = int(inquirer.number(message="Base fee (drops):", default=121).execute())
            reserve_base = int(inquirer.number(message="Reserve base (drops):", default=2_000_000).execute())
            reserve_inc = int(inquirer.number(message="Reserve increment (drops):", default=123_456).execute())

            outdir.mkdir(parents=True, exist_ok=True)
            accounts = generate_accounts(num_accounts)
            write_accounts_json(accounts, outdir / "accounts.json")
            fees = FeeSettings(base_fee_drops=base_fee, reserve_base_drops=reserve_base, reserve_increment_drops=reserve_inc)
            amendments = fetch_amendments(rpc_url) if include_amendments else []
            ledger = assemble_ledger_json(
                accounts=accounts,
                account_ns=LedgerNamespace.ACCOUNT,  # swap to your constant if you removed the Enum
                fees=fees,
                amendments=amendments,
            )
            write_ledger_json(ledger, outdir / "ledger.json")
            typer.echo(f"Wrote {outdir / 'accounts.json'} and {outdir / 'ledger.json'}")

        elif choice == "ledger_show":
            rpc_url = inquirer.text(
                message="RPC URL:", default="https://s.devnet.rippletest.net:51234"
            ).execute()
            enabled_only = inquirer.confirm(message="Enabled only?", default=True).execute()
            amends = fetch_amendments(rpc_url)
            if enabled_only:
                amends = [a for a in amends if a.enabled]
            typer.echo("\nEN  OB  INDEX                                                             NAME")
            for a in amends:
                en = "✓" if a.enabled else " "
                ob = "×" if a.obsolete else " "
                typer.echo(f"{en:<3} {ob:<3} {a.index}  {a.name}")

        elif choice == "compose_write":
            from gl.compose import write_compose_file  # noqa: PLC0415
            from gl.config import ComposeConfig  # noqa: PLC0415

            output_file = Path(inquirer.text(message="Compose output path:", default="compose.yaml").execute())
            validators = int(inquirer.number(message="Validators:", default=1).execute())
            validator_image = inquirer.text(message="Validator image:", default="rippleci/rippled:latest").execute()
            validator_name = inquirer.text(message="Validator name:", default="rippled").execute()
            validator_version = inquirer.text(message="Validator version:", default="2.6.0").execute()
            hubs = int(inquirer.number(message="Hubs:", default=0).execute())

            cfg = ComposeConfig()
            cfg_over = cfg.model_copy(update={
                "num_validators": validators,
                "validator_image": validator_image,
                "validator_name": validator_name,
                "validator_version": validator_version,
                "num_hubs": hubs,
            })

            try:
                write_compose_file(cfg_over, output_file=output_file)
            except TypeError:
                write_compose_file(output_file, cfg_over)

            typer.echo(f"Wrote {output_file.resolve()}")

        else:
            break
