"""Sponsorship ledger object generation for the Sponsor amendment.

Reference: XLS-68 and xrpld's ``keylet::sponsor`` implementation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from generate_ledger.accounts import resolve_account_to_object
from generate_ledger.indices import sponsorship_index

if TYPE_CHECKING:
    from generate_ledger.accounts import Account
    from generate_ledger.ledger import LedgerConfig

LSF_SPONSORSHIP_REQUIRE_SIGN_FOR_FEE = 0x00010000
LSF_SPONSORSHIP_REQUIRE_SIGN_FOR_RESERVE = 0x00020000
SPONSORSHIP_FLAGS_MASK = LSF_SPONSORSHIP_REQUIRE_SIGN_FOR_FEE | LSF_SPONSORSHIP_REQUIRE_SIGN_FOR_RESERVE

ZERO_TXN_ID = "0" * 64
ZERO_NODE = "0000000000000000"


def _positive_amount_or_none(value: str | None, field: str) -> str | None:
    """Normalize optional XRP amount fields encoded as drops strings."""
    if value is None:
        return None
    amount = int(value)
    if amount < 0:
        raise ValueError(f"{field} must be non-negative")
    return str(amount) if amount > 0 else None


def _positive_count_or_none(value: int | None, field: str) -> int | None:
    """Normalize optional UINT32 count fields."""
    if value is None:
        return None
    if value < 0:
        raise ValueError(f"{field} must be non-negative")
    return value if value > 0 else None


def _build_sponsorship_object(
    *,
    owner: str,
    sponsee: str,
    fee_amount: str | None = None,
    max_fee: str | None = None,
    reserve_count: int | None = None,
    flags: int = 0,
    previous_txn_id: str = ZERO_TXN_ID,
    previous_txn_lgr_seq: int = 0,
) -> dict:
    """Build a Sponsorship ledger object dict.

    ``Owner`` is the sponsor and pays the reserve for this object. The object is
    linked from both the owner and sponsee owner directories, but only the owner
    account's ``OwnerCount`` increases.
    """
    if owner == sponsee:
        raise ValueError("Sponsorship owner and sponsee must be different accounts")
    if flags & ~SPONSORSHIP_FLAGS_MASK:
        raise ValueError(f"Unsupported Sponsorship flags: 0x{flags & ~SPONSORSHIP_FLAGS_MASK:08X}")

    normalized_fee_amount = _positive_amount_or_none(fee_amount, "fee_amount")
    normalized_max_fee = _positive_amount_or_none(max_fee, "max_fee")
    normalized_reserve_count = _positive_count_or_none(reserve_count, "reserve_count")

    obj: dict = {
        "LedgerEntryType": "Sponsorship",
        "Flags": flags,
        "Owner": owner,
        "Sponsee": sponsee,
        "OwnerNode": ZERO_NODE,
        "SponseeNode": ZERO_NODE,
        "PreviousTxnID": previous_txn_id,
        "PreviousTxnLgrSeq": previous_txn_lgr_seq,
        "index": sponsorship_index(owner, sponsee),
    }
    if normalized_fee_amount is not None:
        obj["FeeAmount"] = normalized_fee_amount
    if normalized_max_fee is not None:
        obj["MaxFee"] = normalized_max_fee
    if normalized_reserve_count is not None:
        obj["ReserveCount"] = normalized_reserve_count
    return obj


def generate_sponsorship_objects(*, accounts: list[Account], config: LedgerConfig) -> list[dict]:
    """Generate Sponsorship ledger objects from ``config.sponsorships``."""
    objects: list[dict] = []
    for spec in config.sponsorships:
        owner = resolve_account_to_object(spec.owner, accounts)
        sponsee = resolve_account_to_object(spec.sponsee, accounts)
        objects.append(
            _build_sponsorship_object(
                owner=owner.address,
                sponsee=sponsee.address,
                fee_amount=spec.fee_amount,
                max_fee=spec.max_fee,
                reserve_count=spec.reserve_count,
                flags=spec.flags,
            )
        )
    return objects
