"""DirectoryNode consolidation for XRPL genesis ledger assembly.

Handles merging per-object DirectoryNode entries into consolidated
per-account directories with sorted Indexes and OwnerCount tracking.
"""

from generate_ledger.indices import owner_dir


def make_owner_dir_entry(address: str, object_index: str) -> dict:
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


def merge_dir_node(directory_nodes: dict, entry: dict) -> None:
    """Merge a DirectoryNode entry into the consolidated directory_nodes dict."""
    owner = entry["Owner"]
    if owner in directory_nodes:
        directory_nodes[owner]["Indexes"].extend(entry["Indexes"])
    else:
        directory_nodes[owner] = entry.copy()


def consolidate_directory_nodes(
    *,
    trustline_objects: list | None = None,
    amm_objects: list | None = None,
    extra_objects: list[dict] | None = None,
) -> tuple[list[dict], dict[str, dict], dict[str, int]]:
    """Consolidate DirectoryNode entries from trustlines, AMM objects, and extras.

    Returns:
        state_entries: Additional state entries (RippleState, AMM objects, etc.) to add.
        directory_nodes: Consolidated {owner: DirectoryNode} dict with sorted Indexes.
        owner_counts: {address: count} of owned objects per account.
    """
    state_entries: list[dict] = []
    directory_nodes: dict[str, dict] = {}
    owner_counts: dict[str, int] = {}

    # Process trustlines
    if trustline_objects:
        for tl_obj in trustline_objects:
            state_entries.append(tl_obj.ripple_state)

            for dn in [tl_obj.directory_node_a, tl_obj.directory_node_b]:
                merge_dir_node(directory_nodes, dn)

            owner_a = tl_obj.directory_node_a["Owner"]
            owner_b = tl_obj.directory_node_b["Owner"]
            owner_counts[owner_a] = owner_counts.get(owner_a, 0) + 1
            owner_counts[owner_b] = owner_counts.get(owner_b, 0) + 1

    # Process AMM objects
    if amm_objects:
        for amm_obj in amm_objects:
            state_entries.append(amm_obj.amm)
            state_entries.append(amm_obj.amm_account)

            merge_dir_node(directory_nodes, amm_obj.directory_node)

            if amm_obj.lp_token_trustline:
                state_entries.append(amm_obj.lp_token_trustline)

            if amm_obj.asset_trustlines:
                state_entries.extend(amm_obj.asset_trustlines)

            if amm_obj.issuer_directories:
                for issuer_dn in amm_obj.issuer_directories:
                    merge_dir_node(directory_nodes, issuer_dn)

            if amm_obj.creator_lp_directory:
                merge_dir_node(directory_nodes, amm_obj.creator_lp_directory)
                creator_owner = amm_obj.creator_lp_directory["Owner"]
                owner_counts[creator_owner] = owner_counts.get(creator_owner, 0) + 1

    # Process extra objects (MPTokenIssuance, MPToken, etc.)
    if extra_objects:
        for obj in extra_objects:
            state_entries.append(obj)
            le_type = obj.get("LedgerEntryType")
            if le_type == "MPTokenIssuance":
                issuer = obj["Issuer"]
                merge_dir_node(directory_nodes, make_owner_dir_entry(issuer, obj["index"]))
                owner_counts[issuer] = owner_counts.get(issuer, 0) + 1
            elif le_type == "MPToken":
                holder = obj["Account"]
                merge_dir_node(directory_nodes, make_owner_dir_entry(holder, obj["index"]))
                owner_counts[holder] = owner_counts.get(holder, 0) + 1

    # Sort Indexes in each DirectoryNode (XRPL serialization requires sorted STVector256)
    for dn in directory_nodes.values():
        dn["Indexes"].sort()

    return state_entries, directory_nodes, owner_counts
