import json
from collections.abc import Iterable
from pathlib import Path

from generate_ledger.constants import LSF_DEFAULT_RIPPLE
from generate_ledger.directory_nodes import consolidate_directory_nodes
from generate_ledger.indices import account_root_index

GENESIS_ADDRESS = "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh"
TOTAL_COINS_DROPS = int(100e9 * 1e6)  # 100 billion XRP in drops
DEFAULT_ACCOUNT_BALANCE = 100_000_000_000  # 100k XRP in drops


def amendments_to_ledger_entry(amendment_hashes: list[str]) -> dict:
    return {
        "Amendments": amendment_hashes,
        "Flags": 0,
        "LedgerEntryType": "Amendments",
        # Amendments index is always this
        "index": "7DB0788C020F02780A673DC74757F23823FA3014C1866E72CC4CD8B226CD6EF4",
    }


def account_root_entry(
    address: str,
    balance_drops: int,
    flags: int = 0,
    owner_count: int = 0,
    prev_txn_id: str | None = None,
    prev_txn_lgr_seq: int | None = None,
    sequence: int = 2,
    precomputed_index: str | None = None,
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
        "index": precomputed_index if precomputed_index is not None else account_root_index(address),
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
    trustline_objects: list | None = None,
    amm_objects: list | None = None,
    amm_issuers: set[str] | None = None,
    extra_objects: list[dict] | None = None,
    ledger_index: int = 5,
) -> dict:
    """
    Build a minimal 'ledger' object with accountState suitable for bootstrapping a network.
    Genesis account takes remaining XRP after generating other accounts.

    Args:
        trustline_objects: List of TrustlineObjects (from generate_trustlines)
        amm_objects: List of AMMObjects (from generate_amm_objects)
        amm_issuers: Set of issuer addresses that need lsfDefaultRipple flag
        extra_objects: Additional ledger objects (e.g. from develop/ builders)
    """
    balances_total = 0
    state: list[dict] = []
    amm_issuers = amm_issuers or set()

    # Build AccountRoot entries
    for a in accounts:
        flags = LSF_DEFAULT_RIPPLE if a.address in amm_issuers else 0
        state.append(
            account_root_entry(
                address=a.address,
                balance_drops=default_acct_balance,
                flags=flags,
                prev_txn_id="0" * 64,
                prev_txn_lgr_seq=0,
                sequence=2,
                owner_count=0,
                precomputed_index=getattr(a, "account_root_idx", None),
            )
        )
        balances_total += default_acct_balance

    # Consolidate all DirectoryNodes and collect state entries
    extra_state, directory_nodes, owner_counts = consolidate_directory_nodes(
        trustline_objects=trustline_objects,
        amm_objects=amm_objects,
        extra_objects=extra_objects,
    )
    state.extend(extra_state)
    state.extend(directory_nodes.values())

    # Update OwnerCount in AccountRoot entries
    for entry in state:
        if entry.get("LedgerEntryType") == "AccountRoot":
            address = entry["Account"]
            if address in owner_counts:
                entry["OwnerCount"] = owner_counts[address]

    genesis_balance = max(total_coins_drops - balances_total, 0)
    state.insert(
        0,
        account_root_entry(
            address=genesis_address,
            balance_drops=genesis_balance,
            prev_txn_id="0" * 64,
            prev_txn_lgr_seq=0,
            sequence=1,
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
            "totalCoins": str(total_coins_drops),
            "total_coins": str(total_coins_drops),
        }
    }


def write_ledger_json(ledger: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2))
