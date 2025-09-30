# main.py (or a quick script)
from pathlib import Path

from generate_ledger.models.ledger import LedgerNamespace  # your existing enum/type
from gl.indices import LedgerNamespace as NSProtocol       # protocol compatibility

from gl.accounts import generate_accounts, write_accounts_json
from gl.amendments import fetch_amendments
from gl.ledger_build import (
    assemble_ledger_json, write_ledger_json, FeeSettings
)

TESTNET_DIR = Path("testnet")
ACCOUNTS_JSON = TESTNET_DIR / "accounts.json"
LEDGER_JSON = TESTNET_DIR / "ledger.json"

NUM_ACCOUNTS = 40

def main():
    # 1) accounts
    accts = generate_accounts(NUM_ACCOUNTS)
    write_accounts_json(accts, ACCOUNTS_JSON)

    # 2) options
    fees = FeeSettings(base_fee_drops=121, reserve_base_drops=2_000_000, reserve_increment_drops=123_456)
    amends = fetch_amendments()  # or leave empty if fully offline

    # IMPORTANT: supply your existing LedgerNamespace.ACCOUNT (must expose .byte)
    account_ns: NSProtocol = LedgerNamespace.ACCOUNT  # your enum already lives here

    # 3) assemble + write
    ledger = assemble_ledger_json(
        accounts=accts,
        account_ns=account_ns,
        fees=fees,
        amendments=amends,
    )
    write_ledger_json(ledger, LEDGER_JSON)
    print(f"Wrote {LEDGER_JSON.resolve()} and {ACCOUNTS_JSON.resolve()}")

if __name__ == "__main__":
    main()
