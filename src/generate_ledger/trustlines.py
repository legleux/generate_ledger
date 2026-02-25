import random
from binascii import unhexlify
from dataclasses import dataclass

from pydantic_settings import BaseSettings, SettingsConfigDict
from xrpl import CryptoAlgorithm
from xrpl.core.binarycodec import encode, encode_for_signing
from xrpl.core.keypairs import sign
from xrpl.models.transactions import TrustSet
from xrpl.wallet import Wallet

from gl.accounts import Account
from gl.crypto import sha512_half
from gl.indices import owner_dir, ripple_state_index


@dataclass
class Trustline:
    """Represents a trustline specification."""
    account_a: str  # First account address
    account_b: str  # Second account address
    currency: str   # Currency code (e.g., "USD")
    limit: int      # Trust limit amount

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


def generate_trustset_txn_id(
    account: Account, wallet: Wallet, limit_amount: dict, sequence: int, fee: str = "123",
) -> str:
    """
    Generate a TrustSet transaction ID without submitting it.

    This creates a signed TrustSet transaction and computes its hash,
    which is used as the PreviousTxnID for directory nodes.
    """
    ts_txn = TrustSet(
        account=account.address,
        limit_amount=limit_amount,
        sequence=sequence,
        signing_pub_key=wallet.public_key,
        fee=fee,
    )

    # Sign the transaction
    signing_payload_hex = encode_for_signing(ts_txn.to_xrpl())
    signature_hex = sign(bytes.fromhex(signing_payload_hex), wallet.private_key)
    signed_dict = {**ts_txn.to_xrpl(), "TxnSignature": signature_hex}
    tx_blob = encode(signed_dict)

    # Compute transaction ID
    TXN_PREFIX = bytes.fromhex("54584E00")  # "TXN\0"
    txn_id = sha512_half(TXN_PREFIX + unhexlify(tx_blob)).hex().upper()
    return txn_id


def generate_trustline_objects(
    account_a: Account,
    account_b: Account,
    currency: str,
    limit: int,
    ledger_seq: int = 2
) -> TrustlineObjects:
    """
    Generate all 3 ledger objects needed for a trustline:
    1. RippleState (the actual trustline)
    2. DirectoryNode for account_a
    3. DirectoryNode for account_b
    """
    # Create wallets to generate transaction ID
    is_ed = getattr(account_b, "algorithm", "secp256k1") == "ed25519"
    algo = CryptoAlgorithm.ED25519 if is_ed else CryptoAlgorithm.SECP256K1
    wallet_b = Wallet.from_seed(account_b.seed, algorithm=algo)

    # Prepare the limit amount for the TrustSet transaction
    limit_amount = {
        "currency": currency,
        "issuer": account_a.address,
        "value": str(limit)
    }

    # Generate TrustSet transaction ID (used for DirectoryNode PreviousTxnID)
    txn_id = generate_trustset_txn_id(account_b, wallet_b, limit_amount, sequence=4)

    # Calculate the RippleState index
    rsi = ripple_state_index(account_a.address, account_b.address, currency)

    # Determine high/low accounts (lexicographic order)
    a1 = account_a.address.encode()
    a2 = account_b.address.encode()
    if a1 < a2:
        lo_address, hi_address = account_a.address, account_b.address
    else:
        lo_address, hi_address = account_b.address, account_a.address

    # Create RippleState object
    ripple_state = {
        "Balance": {
            "currency": currency,
            "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",  # Neutral issuer for balance
            "value": "0",
        },
        "Flags": 131072,  # lsfLowReserve flag
        "HighLimit": {
            "currency": currency,
            "issuer": hi_address,
            "value": str(limit),
        },
        "HighNode": "0",
        "LedgerEntryType": "RippleState",
        "LowLimit": {
            "currency": currency,
            "issuer": lo_address,
            "value": str(limit),
        },
        "LowNode": "0",
        "PreviousTxnID": txn_id,
        "PreviousTxnLgrSeq": ledger_seq,
        "index": rsi,
    }

    # Create DirectoryNode for account_a
    root_index_a = owner_dir(account_a.address)
    directory_node_a = {
        "Flags": 0,
        "Indexes": [rsi],
        "LedgerEntryType": "DirectoryNode",
        "Owner": account_a.address,
        "PreviousTxnID": txn_id,
        "PreviousTxnLgrSeq": ledger_seq,
        "RootIndex": root_index_a,
        "index": root_index_a,
    }

    # Create DirectoryNode for account_b
    root_index_b = owner_dir(account_b.address)
    directory_node_b = {
        "Flags": 0,
        "Indexes": [rsi],
        "LedgerEntryType": "DirectoryNode",
        "Owner": account_b.address,
        "PreviousTxnID": txn_id,
        "PreviousTxnLgrSeq": ledger_seq,
        "RootIndex": root_index_b,
        "index": root_index_b,
    }

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
