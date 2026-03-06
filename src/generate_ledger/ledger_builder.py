import json
from collections.abc import Iterable
from pathlib import Path

from pydantic import PositiveInt

from generate_ledger.accounts import generate_accounts
from generate_ledger.constants import LSF_DEFAULT_RIPPLE
from generate_ledger.indices import account_root_index, owner_dir

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


def _make_owner_dir_entry(address: str, object_index: str) -> dict:
    """Create a minimal DirectoryNode entry for a single object in an account's owner dir."""
    dir_idx = owner_dir(address)
    return {
        "Flags": 0,
        "Indexes": [object_index],
        "LedgerEntryType": "DirectoryNode",
        "Owner": address,
        "RootIndex": dir_idx,
        "index": dir_idx,
    }


def _merge_dir_node(directory_nodes: dict, entry: dict) -> None:
    """Merge a DirectoryNode entry into the consolidated directory_nodes dict."""
    owner = entry["Owner"]
    if owner in directory_nodes:
        directory_nodes[owner]["Indexes"].extend(entry["Indexes"])
    else:
        directory_nodes[owner] = entry.copy()


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

    #  Track which accounts have trustlines for OwnerCount
    account_owner_counts = {}

    for a in accounts:
        # Set lsfDefaultRipple flag for AMM token issuers
        flags = LSF_DEFAULT_RIPPLE if a.address in amm_issuers else 0

        state.append(
            account_root_entry(
                address=a.address,
                balance_drops=default_acct_balance,
                flags=flags,
                prev_txn_id="0" * 64,
                prev_txn_lgr_seq=0,
                sequence=2,
                owner_count=0,  # Will update below if trustlines exist
                precomputed_index=getattr(a, "account_root_idx", None),
            )
        )
        balances_total += default_acct_balance
        account_owner_counts[a.address] = 0

    # Add trustlines and consolidate directory nodes
    directory_nodes = {}  # owner -> DirectoryNode dict

    if trustline_objects:
        for tl_obj in trustline_objects:
            # Add RippleState
            state.append(tl_obj.ripple_state)

            # Consolidate DirectoryNodes by owner
            for dn in [tl_obj.directory_node_a, tl_obj.directory_node_b]:
                owner = dn["Owner"]
                if owner in directory_nodes:
                    # Merge Indexes arrays
                    directory_nodes[owner]["Indexes"].extend(dn["Indexes"])
                else:
                    directory_nodes[owner] = dn.copy()

            # Update owner counts
            owner_a = tl_obj.directory_node_a["Owner"]
            owner_b = tl_obj.directory_node_b["Owner"]
            account_owner_counts[owner_a] = account_owner_counts.get(owner_a, 0) + 1
            account_owner_counts[owner_b] = account_owner_counts.get(owner_b, 0) + 1

    # Add AMM objects
    if amm_objects:
        for amm_obj in amm_objects:
            # Add AMM ledger object
            state.append(amm_obj.amm)

            # Add AMM pseudo-account
            state.append(amm_obj.amm_account)

            # Consolidate DirectoryNode for AMM account
            dn = amm_obj.directory_node
            owner = dn["Owner"]
            if owner in directory_nodes:
                directory_nodes[owner]["Indexes"].extend(dn["Indexes"])
            else:
                directory_nodes[owner] = dn.copy()

            # Add LP token trustline if present
            if amm_obj.lp_token_trustline:
                state.append(amm_obj.lp_token_trustline)

            # Add asset trustlines (deposited tokens held by AMM)
            if amm_obj.asset_trustlines:
                for asset_tl in amm_obj.asset_trustlines:
                    state.append(asset_tl)

            # Consolidate issuer directories for asset trustlines
            # (RippleState must be in BOTH parties' directories)
            if amm_obj.issuer_directories:
                for issuer_dn in amm_obj.issuer_directories:
                    issuer_owner = issuer_dn["Owner"]
                    if issuer_owner in directory_nodes:
                        directory_nodes[issuer_owner]["Indexes"].extend(issuer_dn["Indexes"])
                    else:
                        directory_nodes[issuer_owner] = issuer_dn.copy()

            # Consolidate creator's LP token directory if present
            if amm_obj.creator_lp_directory:
                creator_dn = amm_obj.creator_lp_directory
                creator_owner = creator_dn["Owner"]
                if creator_owner in directory_nodes:
                    directory_nodes[creator_owner]["Indexes"].extend(creator_dn["Indexes"])
                else:
                    directory_nodes[creator_owner] = creator_dn.copy()
                # Update creator's owner count
                account_owner_counts[creator_owner] = account_owner_counts.get(creator_owner, 0) + 1

    # Add extra objects (from develop/ builders or other sources)
    # MPTokenIssuance and MPToken objects get DirectoryNode entries and OwnerCount updates.
    if extra_objects:
        for obj in extra_objects:
            state.append(obj)
            le_type = obj.get("LedgerEntryType")
            if le_type == "MPTokenIssuance":
                issuer = obj["Issuer"]
                _merge_dir_node(directory_nodes, _make_owner_dir_entry(issuer, obj["index"]))
                account_owner_counts[issuer] = account_owner_counts.get(issuer, 0) + 1
            elif le_type == "MPToken":
                holder = obj["Account"]
                _merge_dir_node(directory_nodes, _make_owner_dir_entry(holder, obj["index"]))
                account_owner_counts[holder] = account_owner_counts.get(holder, 0) + 1

    # Sort Indexes in each DirectoryNode (XRPL serialization requires sorted STVector256)
    for dn in directory_nodes.values():
        dn["Indexes"].sort()

    # Add consolidated DirectoryNodes to state
    state.extend(directory_nodes.values())

    # Update OwnerCount in AccountRoot entries
    for entry in state:
        if entry.get("LedgerEntryType") == "AccountRoot":
            address = entry["Account"]
            if address in account_owner_counts:
                entry["OwnerCount"] = account_owner_counts[address]

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
