"""MPToken (Multi-Purpose Token) ledger object generation.

Generates MPTokenIssuance and MPToken ledger objects for pre-populating
a genesis ledger.  This module lives in ``develop/`` because MPT requires
the ``MPTokensV1`` amendment which is only available in xrpld's develop
branch.

Reference: XLS-33d, xrpld Indexes.cpp (keylet::mptIssuance / keylet::mptoken)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from generate_ledger.accounts import resolve_account_to_object
from generate_ledger.indices import mpt_id_to_hex, mpt_issuance_index, mptoken_index

if TYPE_CHECKING:
    from generate_ledger.accounts import Account
    from generate_ledger.ledger import LedgerConfig


# Alias for local use; resolve_account_to_object is the canonical version in accounts.py
_resolve_account = resolve_account_to_object


def _build_issuance_object(
    issuer_address: str,
    sequence: int,
    flags: int = 0,
    max_amount: str | None = None,
    asset_scale: int | None = None,
    transfer_fee: int | None = None,
    metadata: str | None = None,
) -> dict:
    """Build an MPTokenIssuance ledger object dict.

    Fields match what xrpld's MPTokenIssuanceCreate sets on the SLE:
        sfFlags, sfIssuer, sfOutstandingAmount, sfOwnerNode, sfSequence
    plus optional: sfMaximumAmount, sfAssetScale, sfTransferFee, sfMPTokenMetadata
    """
    idx = mpt_issuance_index(sequence, issuer_address)
    obj: dict = {
        "LedgerEntryType": "MPTokenIssuance",
        "Flags": flags,
        "Issuer": issuer_address,
        "Sequence": sequence,
        "OutstandingAmount": "0",
        "OwnerNode": "0000000000000000",
        "PreviousTxnID": "0" * 64,
        "PreviousTxnLgrSeq": 0,
        "index": idx,
    }
    if max_amount is not None:
        obj["MaximumAmount"] = max_amount
    if asset_scale is not None:
        obj["AssetScale"] = asset_scale
    if transfer_fee is not None:
        obj["TransferFee"] = transfer_fee
    if metadata is not None:
        obj["MPTokenMetadata"] = metadata
    return obj


def _build_mptoken_object(
    issuance_index_hex: str,
    issuance_id_hex: str,
    holder_address: str,
    amount: str,
    flags: int = 0,
) -> dict:
    """Build an MPToken ledger object dict for a specific holder.

    Fields:
        sfAccount, sfMPTokenIssuanceID, sfMPTAmount, sfOwnerNode, sfFlags
    """
    idx = mptoken_index(issuance_index_hex, holder_address)
    return {
        "LedgerEntryType": "MPToken",
        "Account": holder_address,
        "MPTokenIssuanceID": issuance_id_hex,
        "MPTAmount": amount,
        "OwnerNode": "0000000000000000",
        "Flags": flags,
        "PreviousTxnID": "0" * 64,
        "PreviousTxnLgrSeq": 0,
        "index": idx,
    }


def _outstanding_amount(holders: list) -> str:
    """Sum all holder amounts to compute OutstandingAmount on the issuance."""
    total = sum(int(h.amount) for h in holders)
    return str(total)


def generate_mpt_objects(
    *,
    accounts: list[Account],
    config: LedgerConfig,
) -> list[dict]:
    """Generate MPToken ledger objects from config.mpt_issuances.

    Returns a flat list of dicts:
      - One MPTokenIssuance per configured issuance
      - One MPToken per holder per issuance (if holders are configured)

    ledger_builder.py scans this list by LedgerEntryType to create the
    appropriate DirectoryNode entries and update OwnerCount values.
    """
    if not config.mpt_issuances:
        return []

    objects: list[dict] = []

    for spec in config.mpt_issuances:
        issuer_acct = _resolve_account(spec.issuer, accounts)
        issuance_idx = mpt_issuance_index(spec.sequence, issuer_acct.address)
        issuance_id_hex = mpt_id_to_hex(spec.sequence, issuer_acct.address)

        # Build outstanding amount from all holders
        outstanding = _outstanding_amount(spec.holders) if spec.holders else "0"

        issuance_obj = _build_issuance_object(
            issuer_address=issuer_acct.address,
            sequence=spec.sequence,
            flags=spec.flags,
            max_amount=spec.max_amount,
            asset_scale=spec.asset_scale,
            transfer_fee=spec.transfer_fee,
            metadata=spec.metadata,
        )
        issuance_obj["OutstandingAmount"] = outstanding
        objects.append(issuance_obj)

        for holder_spec in spec.holders:
            holder_acct = _resolve_account(holder_spec.holder, accounts)
            mptoken_obj = _build_mptoken_object(
                issuance_index_hex=issuance_idx,
                issuance_id_hex=issuance_id_hex,
                holder_address=holder_acct.address,
                amount=holder_spec.amount,
            )
            objects.append(mptoken_obj)

    return objects
