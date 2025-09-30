import json
from pathlib import Path
from typing import Iterable

from gl.accounts import generate_accounts
from gl.indices import account_root_index
from pydantic import PositiveInt

GENESIS_ADDRESS = "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh"
TOTAL_COINS_DROPS = int(100e9 * 1e6)  # 100 billion XRP in drops
DEFAULT_ACCOUNT_BALANCE = 100_000_000_000  # 100k XRP in drops

def amendments_to_ledger_entry(amendment_hashes: list[str]) -> dict:
    return {
        "Amendments": amendment_hashes,
        "Flags": 0,
        "LedgerEntryType": "Amendments",
        # Amendments index is always this
        "index": "7DB0788C020F02780A673DC74757F23823FA3014C1866E72CC4CD8B226CD6EF4"

    }

def generate_account_creds(num_accounts: PositiveInt):
    accts = generate_accounts(num_accounts)
    return accts

def account_root_entry(
    address: str,
    balance_drops: int,
    flags: int = 0,
    owner_count: int = 0,
    prev_txn_id: str | None = None,
    prev_txn_lgr_seq: int | None = None,
    sequence: int = 2,
) -> dict:
    entry = {
        "Account": address,
        "Balance": str(balance_drops),
        "Flags": flags,
        "LedgerEntryType": "AccountRoot",
        "OwnerCount": owner_count,
        "PreviousTxnID": "0" * 64,
        "PreviousTxnLgrSeq": sequence - 1,
        "Sequence": sequence,
        "index": account_root_index(address),
    }
    if prev_txn_id is not None:
        entry["PreviousTxnID"] = prev_txn_id
    if prev_txn_lgr_seq is not None:
        entry["PreviousTxnLgrSeq"] = prev_txn_lgr_seq
    return entry

def assemble_ledger_json(
    *,
    accounts: Iterable[tuple[str, str]],
    total_coins_drops: int = TOTAL_COINS_DROPS,
    default_acct_balance: int = DEFAULT_ACCOUNT_BALANCE,
    genesis_address: str = GENESIS_ADDRESS,
    fees: dict | None = None,
    amendment_hashes: list[str],
    ledger_index: int = 5,
) -> dict:
    """
    Build a minimal 'ledger' object with accountState suitable for bootstrapping a network.
    Genesis account takes remaining XRP after generating other accounts.
    """
    balances_total = 0
    state: list[dict] = []

    for a in accounts:
        state.append(
            account_root_entry(
                address=a.address,
                balance_drops=default_acct_balance,
                prev_txn_id="0" * 64,
                prev_txn_lgr_seq=0,
                sequence=2
            )
        )
        balances_total += default_acct_balance

    genesis_balance = max(total_coins_drops - balances_total, 0)
    state.insert(
        0,
        account_root_entry(
            address=genesis_address,
            balance_drops=genesis_balance,
            prev_txn_id="0" * 64,
            prev_txn_lgr_seq=0,
            sequence=1,
            # index="2B6AC232AA4C4BE41BF49D2459FA4A0347E1B543A4C92FCEE0821C0201E2E9A8",
        ),
    )

    if fees:
        state.append(fees)
    state.append(amendments_to_ledger_entry(amendment_hashes))

    return {
        "ledger": {
            "accepted": True,
            "accountState": state,
            "close_time_resolution": 10,
            # "closed": True,
            # "hash": "56DA0940767AC2F17F0E384F04816002403D0756432B9D503DDA20128A2AAF11",
            # "ledger_hash": "56DA0940767AC2F17F0E384F04816002403D0756432B9D503DDA20128A2AAF11",
            # "ledger_index": "2",
            # "parent_close_time": 733708800,
            # "parent_hash": "56DA0940767AC2F17F0E384F04816002403D0756432B9D503DDA20128A2AAF11",
            # "seqNum": "2",
            "totalCoins": str(total_coins_drops),
            "total_coins": str(total_coins_drops),
        }
    }

def write_ledger_json(ledger: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2))
