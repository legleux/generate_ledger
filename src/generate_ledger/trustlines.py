import random
from dataclasses import dataclass

from pydantic_settings import BaseSettings, SettingsConfigDict
from xrpl.core.addresscodec import decode_classic_address

from generate_ledger.accounts import Account
from generate_ledger.constants import NEUTRAL_ISSUER
from generate_ledger.indices import owner_dir, ripple_state_index


@dataclass
class Trustline:
    """Represents a trustline specification."""

    account_a: str  # First account address
    account_b: str  # Second account address
    currency: str  # Currency code (e.g., "USD")
    limit: int  # Trust limit amount


@dataclass
class TrustlineObjects:
    """Complete set of ledger objects for a trustline."""

    ripple_state: dict
    directory_node_a: dict
    directory_node_b: dict


class TrustlineConfig(BaseSettings):
    """Configuration for trustline generation."""

    model_config = SettingsConfigDict(env_prefix="GL_TRUSTLINE_", env_file=".env")

    num_trustlines: int = 0  # Number of random trustlines to generate
    currencies: list[str] = ["USD", "EUR", "GBP"]  # Available currencies for random generation
    default_limit: str = str(int(100e9))  # Default trust limit (100B units)
    ledger_seq: int = 2  # Ledger sequence for PreviousTxnLgrSeq


# TODO: remove generate_trustset_txn_id entirely once confirmed xrpld ignores PreviousTxnID on genesis ledger objects
# def generate_trustset_txn_id(account, limit_amount, sequence, fee="123") -> str:
#     """Generate a TrustSet transaction ID without submitting it."""
#     ...  # was: sign_and_hash_txn(TrustSet(...), account.seed, ...)


def _placeholder_txn_id() -> str:
    """Placeholder PreviousTxnID — xrpld ignores this field on genesis ledger objects."""
    return "0" * 64


def generate_trustline_objects(
    account_a: Account, account_b: Account, currency: str, limit: int, ledger_seq: int = 2
) -> TrustlineObjects:
    """
    Generate all 3 ledger objects needed for a trustline:
    1. RippleState (the actual trustline)
    2. DirectoryNode for account_a
    3. DirectoryNode for account_b
    """
    txn_id = _placeholder_txn_id()

    # Calculate the RippleState index
    rsi = ripple_state_index(account_a.address, account_b.address, currency)

    lo_address, hi_address = order_low_high(account_a.address, account_b.address)

    ripple_state = build_ripple_state(
        currency=currency,
        lo_address=lo_address,
        hi_address=hi_address,
        balance_value="0",
        lo_limit=str(limit),
        hi_limit=str(limit),
        flags=131072,  # lsfLowReserve
        txn_id=txn_id,
        ledger_seq=ledger_seq,
        index=rsi,
    )
    directory_node_a = build_directory_node(
        index=owner_dir(account_a.address),
        entries=[rsi],
        owner=account_a.address,
        txn_id=txn_id,
        ledger_seq=ledger_seq,
    )
    directory_node_b = build_directory_node(
        index=owner_dir(account_b.address),
        entries=[rsi],
        owner=account_b.address,
        txn_id=txn_id,
        ledger_seq=ledger_seq,
    )

    return TrustlineObjects(
        ripple_state=ripple_state,
        directory_node_a=directory_node_a,
        directory_node_b=directory_node_b,
    )


def order_low_high(addr_a: str, addr_b: str) -> tuple[str, str]:
    """Return (lo, hi) addresses ordered by raw AccountID bytes, matching xrpld."""
    if decode_classic_address(addr_a) < decode_classic_address(addr_b):
        return addr_a, addr_b
    return addr_b, addr_a


def build_ripple_state(
    currency: str,
    lo_address: str,
    hi_address: str,
    balance_value: str,
    lo_limit: str,
    hi_limit: str,
    flags: int,
    txn_id: str,
    ledger_seq: int,
    index: str,
) -> dict:
    """Build a RippleState ledger object dict."""
    return {
        "Balance": {
            "currency": currency,
            "issuer": NEUTRAL_ISSUER,
            "value": balance_value,
        },
        "Flags": flags,
        "HighLimit": {
            "currency": currency,
            "issuer": hi_address,
            "value": hi_limit,
        },
        "HighNode": "0",
        "LedgerEntryType": "RippleState",
        "LowLimit": {
            "currency": currency,
            "issuer": lo_address,
            "value": lo_limit,
        },
        "LowNode": "0",
        "PreviousTxnID": txn_id,
        "PreviousTxnLgrSeq": ledger_seq,
        "index": index,
    }


def build_directory_node(
    index: str,
    entries: list[str],
    owner: str,
    txn_id: str,
    ledger_seq: int,
    flags: int = 0,
) -> dict:
    """Build a DirectoryNode ledger object dict."""
    return {
        "Flags": flags,
        "Indexes": list(entries),
        "LedgerEntryType": "DirectoryNode",
        "Owner": owner,
        "PreviousTxnID": txn_id,
        "PreviousTxnLgrSeq": ledger_seq,
        "RootIndex": index,
        "index": index,
    }


def generate_trustline_objects_fast(
    account_a: Account,
    account_b: Account,
    currency: str,
    limit: int,
    ledger_seq: int = 2,
) -> TrustlineObjects:
    """Generate trustline objects without signing a TrustSet transaction.

    Uses the RippleState index as a synthetic PreviousTxnID.  This is valid
    for genesis ledgers — xrpld does not validate PreviousTxnID on bootstrap.
    ~100x faster than generate_trustline_objects() because it skips
    Wallet.from_seed() and xrpl-py transaction signing.
    """
    rsi = ripple_state_index(account_a.address, account_b.address, currency)
    lo_address, hi_address = order_low_high(account_a.address, account_b.address)
    txn_id = rsi  # Synthetic PreviousTxnID: deterministic, unique per trustline

    ripple_state = build_ripple_state(
        currency=currency,
        lo_address=lo_address,
        hi_address=hi_address,
        balance_value="0",
        lo_limit=str(limit),
        hi_limit=str(limit),
        flags=131072,  # lsfLowReserve
        txn_id=txn_id,
        ledger_seq=ledger_seq,
        index=rsi,
    )
    directory_node_a = build_directory_node(
        index=owner_dir(account_a.address),
        entries=[rsi],
        owner=account_a.address,
        txn_id=txn_id,
        ledger_seq=ledger_seq,
    )
    directory_node_b = build_directory_node(
        index=owner_dir(account_b.address),
        entries=[rsi],
        owner=account_b.address,
        txn_id=txn_id,
        ledger_seq=ledger_seq,
    )

    return TrustlineObjects(
        ripple_state=ripple_state,
        directory_node_a=directory_node_a,
        directory_node_b=directory_node_b,
    )


def generate_trustlines(accounts: list[Account], config: TrustlineConfig | None = None) -> list[TrustlineObjects]:
    """
    Generate random trustlines between accounts.

    Args:
        accounts: List of Account objects to create trustlines between
        config: Optional configuration for trustline generation

    Returns:
        List of TrustlineObjects (each contains RippleState + 2 DirectoryNodes)
    """
    cfg = config or TrustlineConfig()

    if cfg.num_trustlines == 0:
        return []

    MIN_ACCOUNTS = 2
    if len(accounts) < MIN_ACCOUNTS:
        raise ValueError("Need at least 2 accounts to create trustlines")

    trustlines = []
    created_pairs = set()  # Track (account_a, account_b, currency) to avoid duplicates

    for _ in range(cfg.num_trustlines):
        # Pick two random different accounts
        account_a, account_b = random.sample(accounts, 2)

        # Pick a random currency
        currency = random.choice(cfg.currencies)

        # Check if this trustline already exists
        pair_key = (*sorted([account_a.address, account_b.address]), currency)
        if pair_key in created_pairs:
            continue

        created_pairs.add(pair_key)

        # Generate the trustline objects
        tl_objects = generate_trustline_objects(
            account_a=account_a,
            account_b=account_b,
            currency=currency,
            limit=int(cfg.default_limit),
            ledger_seq=cfg.ledger_seq,
        )

        trustlines.append(tl_objects)

    return trustlines
