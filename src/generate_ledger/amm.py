"""
AMM (Automated Market Maker) ledger object generation.

Generates AMM pools with:
- AMM ledger object
- AMM pseudo-account (AccountRoot)
- DirectoryNode for the AMM account
"""

import math
from dataclasses import dataclass

from pydantic_settings import BaseSettings, SettingsConfigDict
from xrpl import CryptoAlgorithm
from xrpl.models.transactions import AMMCreate
from xrpl.wallet import Wallet

from generate_ledger.accounts import Account
from generate_ledger.constants import (
    AMM_ACCOUNT_FLAGS,
    LSF_AMM_NODE,
    LSF_DEFAULT_RIPPLE,  # noqa: F401 (re-exported, used by tests)
    LSF_DEPOSIT_AUTH,  # noqa: F401 (re-exported, used by tests)
    LSF_DISABLE_MASTER,  # noqa: F401 (re-exported, used by tests)
)
from generate_ledger.crypto import sign_and_hash_txn
from generate_ledger.indices import amm_account_id, amm_index, amm_lpt_currency, owner_dir, ripple_state_index
from generate_ledger.trustlines import build_directory_node, build_ripple_state, order_low_high


@dataclass
class Asset:
    """Represents an asset in an AMM pool."""

    currency: str | None  # None for XRP
    issuer: str | None  # None for XRP
    amount: str  # Amount as string (drops for XRP, value for issued)

    def is_xrp(self) -> bool:
        return self.currency is None and self.issuer is None

    def to_amount_dict(self) -> dict:
        """Convert to XRPL Amount format."""
        if self.is_xrp():
            return self.amount  # XRP is just a string of drops
        return {
            "currency": self.currency,
            "issuer": self.issuer,
            "value": self.amount,
        }

    def to_issue_dict(self) -> dict:
        """Convert to XRPL Issue format (currency + issuer, no amount)."""
        if self.is_xrp():
            return {"currency": "XRP"}
        return {
            "currency": self.currency,
            "issuer": self.issuer,
        }


@dataclass
class AMMSpec:
    """Specification for an AMM pool to create."""

    asset1: Asset
    asset2: Asset
    trading_fee: int = 500  # Basis points (500 = 0.5%)
    creator: Account | None = None  # Account that creates the AMM (for auction/vote slots)


@dataclass
class AMMObjects:
    """Complete set of ledger objects for an AMM."""

    amm: dict  # AMM ledger object
    amm_account: dict  # AMM pseudo-account (AccountRoot)
    directory_node: dict  # DirectoryNode for AMM account
    lp_token_trustline: dict | None = None  # RippleState for LP tokens (if creator specified)
    creator_lp_directory: dict | None = None  # DirectoryNode for creator's LP token
    asset_trustlines: list[dict] | None = None  # RippleState for deposited tokens (AMM <-> issuer)
    issuer_directories: list[dict] | None = None  # DirectoryNode entries for issuers (for asset trustlines)


class AMMConfig(BaseSettings):
    """Configuration for AMM generation."""

    model_config = SettingsConfigDict(env_prefix="GL_AMM_", env_file=".env")

    ledger_seq: int = 2  # Ledger sequence for PreviousTxnLgrSeq


def calculate_lp_tokens(asset1: Asset, asset2: Asset) -> str:
    """
    Calculate initial LP token amount using geometric mean.

    Formula: sqrt(asset1 * asset2)

    For XRP, amount is in drops (1 XRP = 1,000,000 drops).
    For issued currencies, amount is the value.
    """
    # Convert to numeric values
    amount1 = float(asset1.amount)
    amount2 = float(asset2.amount)

    # Geometric mean
    lp_tokens = math.sqrt(amount1 * amount2)

    # Return as string with appropriate precision
    # For IOU amounts, use scientific notation if very large
    LP_SCIENTIFIC_THRESHOLD = 1e15
    if lp_tokens >= LP_SCIENTIFIC_THRESHOLD:
        return f"{lp_tokens:.15g}"
    return str(int(lp_tokens)) if lp_tokens == int(lp_tokens) else f"{lp_tokens:.15g}"


def generate_ammcreate_txn_id(
    creator: Account,
    asset1: Asset,
    asset2: Asset,
    trading_fee: int,
    sequence: int = 1,
    fee: str = "10000000",  # 10 XRP (AMMCreate requires owner reserve as fee)
) -> str:
    """
    Generate an AMMCreate transaction ID without submitting it.

    This creates a signed AMMCreate transaction and computes its hash,
    which is used as the PreviousTxnID for ledger objects.
    """
    is_ed = getattr(creator, "algorithm", "secp256k1") == "ed25519"
    algo = CryptoAlgorithm.ED25519 if is_ed else CryptoAlgorithm.SECP256K1
    wallet = Wallet.from_seed(creator.seed, algorithm=algo)

    amm_create = AMMCreate(
        account=creator.address,
        amount=asset1.to_amount_dict(),
        amount2=asset2.to_amount_dict(),
        trading_fee=trading_fee,
        sequence=sequence,
        signing_pub_key=wallet.public_key,
        fee=fee,
    )

    return sign_and_hash_txn(amm_create, creator.seed, getattr(creator, "algorithm", "secp256k1"))


def generate_amm_objects(
    spec: AMMSpec,
    ledger_seq: int = 2,
) -> AMMObjects:
    """
    Generate all ledger objects needed for an AMM:
    1. AMM ledger object
    2. AMM pseudo-account (AccountRoot)
    3. DirectoryNode for the AMM account

    Args:
        spec: AMM specification (assets, trading fee, creator)
        ledger_seq: Ledger sequence for PreviousTxnLgrSeq

    Returns:
        AMMObjects containing all required ledger objects
    """
    asset1 = spec.asset1
    asset2 = spec.asset2

    # Calculate AMM index
    idx = amm_index(
        asset1.issuer,
        asset1.currency,
        asset2.issuer,
        asset2.currency,
    )

    # Derive AMM account address (for genesis, parent_hash is all zeros)
    amm_account_address = amm_account_id(idx)

    # Derive LP token currency (uses only currencies, not issuers)
    lpt_currency = amm_lpt_currency(asset1.currency, asset2.currency)

    # Calculate initial LP tokens
    lp_token_amount = calculate_lp_tokens(asset1, asset2)

    # Generate transaction ID if we have a creator
    if spec.creator:
        txn_id = generate_ammcreate_txn_id(spec.creator, asset1, asset2, spec.trading_fee)
    else:
        # Use a placeholder for genesis without specific creator
        txn_id = "0" * 64

    # Build LP token balance
    lp_token_balance = {
        "currency": lpt_currency,
        "issuer": amm_account_address,
        "value": lp_token_amount,
    }

    # Build AMM object
    amm_obj = {
        "Account": amm_account_address,
        "Asset": asset1.to_issue_dict(),
        "Asset2": asset2.to_issue_dict(),
        "Flags": 0,
        "LPTokenBalance": lp_token_balance,
        "LedgerEntryType": "AMM",
        "OwnerNode": "0",
        "PreviousTxnID": txn_id,
        "PreviousTxnLgrSeq": ledger_seq,
        "TradingFee": spec.trading_fee,
        "index": idx,
    }

    # Add auction slot and vote slots if creator specified
    if spec.creator:
        # Auction slot for creator
        # Expiration must be >= TOTAL_TIME_SLOT_SECS (86400 = 24 hours) per rippled assertion
        # Use a far-future value (year 2100 in Ripple epoch) to avoid expiration issues
        # Ripple epoch: seconds since Jan 1, 2000 00:00:00 UTC
        RIPPLE_EPOCH_FAR_FUTURE = 3155760000  # ~year 2100
        amm_obj["AuctionSlot"] = {
            "Account": spec.creator.address,
            "DiscountedFee": spec.trading_fee // 10,  # 10% of trading fee
            "Expiration": RIPPLE_EPOCH_FAR_FUTURE,
            "Price": {
                "currency": lpt_currency,
                "issuer": amm_account_address,
                "value": "0",
            },
        }

        # Vote slot for creator (100% vote weight since only LP)
        amm_obj["VoteSlots"] = [
            {
                "VoteEntry": {
                    "Account": spec.creator.address,
                    "TradingFee": spec.trading_fee,
                    "VoteWeight": 100000,  # 100% in basis points * 1000
                }
            }
        ]

    # Build AMM pseudo-account (AccountRoot)
    # For XRP/token pools, the AMM account holds the XRP deposited
    amm_balance = asset1.amount if asset1.is_xrp() else "0"
    if asset2.is_xrp():
        amm_balance = asset2.amount

    amm_account_obj = {
        "Account": amm_account_address,
        "Balance": amm_balance,  # XRP held by AMM (drops)
        "Flags": AMM_ACCOUNT_FLAGS,
        "LedgerEntryType": "AccountRoot",
        "OwnerCount": 1,  # Only owns the AMM object (LP trustline reserve is on LP holder's side)
        "PreviousTxnID": txn_id,
        "PreviousTxnLgrSeq": ledger_seq,
        "Sequence": 0,  # Pseudo-accounts have sequence 0
        "AMMID": idx,  # Links account to AMM
        "index": "",  # Will be calculated
    }

    # Calculate AccountRoot index for AMM account
    from generate_ledger.indices import account_root_index  # noqa: PLC0415

    amm_account_obj["index"] = account_root_index(amm_account_address)

    # Build DirectoryNode for AMM account
    root_index = owner_dir(amm_account_address)
    directory_node = {
        "Flags": 0,
        "Indexes": [idx],  # AMM object index
        "LedgerEntryType": "DirectoryNode",
        "Owner": amm_account_address,
        "PreviousTxnID": txn_id,
        "PreviousTxnLgrSeq": ledger_seq,
        "RootIndex": root_index,
        "index": root_index,
    }

    # Build LP token trustline and directory node for creator
    lp_token_trustline = None
    creator_lp_directory = None

    if spec.creator:
        # Calculate RippleState index for LP token trustline
        lpt_rs_index = ripple_state_index(
            amm_account_address,
            spec.creator.address,
            lpt_currency,
        )

        lo_address, hi_address = order_low_high(amm_account_address, spec.creator.address)
        # Balance sign: positive if AMM is lo (AMM holds tokens), negative if creator is lo
        if lo_address == amm_account_address:
            balance_value = f"-{lp_token_amount}"  # Creator is hi, holds tokens
        else:
            balance_value = lp_token_amount  # Creator is lo, holds tokens

        # Build LP token RippleState (AMM trustlines have 0 limit and lsfAMMNode flag)
        lp_token_trustline = build_ripple_state(
            currency=lpt_currency,
            lo_address=lo_address,
            hi_address=hi_address,
            balance_value=balance_value,
            lo_limit="0",
            hi_limit="0",
            flags=LSF_AMM_NODE,
            txn_id=txn_id,
            ledger_seq=ledger_seq,
            index=lpt_rs_index,
        )

        # Add LP token trustline index to AMM account's directory
        directory_node["Indexes"].append(lpt_rs_index)

        # Build DirectoryNode for creator's LP token holding
        creator_lp_directory = build_directory_node(
            index=owner_dir(spec.creator.address),
            entries=[lpt_rs_index],
            owner=spec.creator.address,
            txn_id=txn_id,
            ledger_seq=ledger_seq,
        )

        # Note: AMM account OwnerCount stays at 1 (just the AMM object)
        # The LP trustline reserve is on the LP holder's (creator's) side

    # Build trustlines for deposited tokens (non-XRP assets)
    # These represent the tokens held by the AMM, with lsfAMMNode flag
    asset_trustlines = []
    issuer_directories = []

    for asset in [asset1, asset2]:
        if asset.is_xrp():
            continue  # XRP is held as Balance, not as trustline

        # Create RippleState between AMM account and token issuer
        asset_rs_index = ripple_state_index(
            amm_account_address,
            asset.issuer,
            asset.currency,
        )

        lo_address, hi_address = order_low_high(amm_account_address, asset.issuer)
        # Balance sign: positive from lo's perspective means lo holds tokens
        asset_balance_value = asset.amount if lo_address == amm_account_address else f"-{asset.amount}"

        asset_trustline = build_ripple_state(
            currency=asset.currency,
            lo_address=lo_address,
            hi_address=hi_address,
            balance_value=asset_balance_value,
            lo_limit="0",
            hi_limit="0",
            flags=LSF_AMM_NODE,
            txn_id=txn_id,
            ledger_seq=ledger_seq,
            index=asset_rs_index,
        )
        asset_trustlines.append(asset_trustline)

        # Add to AMM account's directory
        directory_node["Indexes"].append(asset_rs_index)

        # Create issuer's directory entry (RippleState must be in BOTH parties' directories)
        issuer_dir = build_directory_node(
            index=owner_dir(asset.issuer),
            entries=[asset_rs_index],
            owner=asset.issuer,
            txn_id=txn_id,
            ledger_seq=ledger_seq,
        )
        issuer_directories.append(issuer_dir)

    return AMMObjects(
        amm=amm_obj,
        amm_account=amm_account_obj,
        directory_node=directory_node,
        lp_token_trustline=lp_token_trustline,
        creator_lp_directory=creator_lp_directory,
        asset_trustlines=asset_trustlines if asset_trustlines else None,
        issuer_directories=issuer_directories if issuer_directories else None,
    )


def generate_amms(
    specs: list[AMMSpec],
    config: AMMConfig | None = None,
) -> list[AMMObjects]:
    """
    Generate AMM objects from a list of specifications.

    Args:
        specs: List of AMM specifications
        config: Optional configuration

    Returns:
        List of AMMObjects (each contains AMM + AccountRoot + DirectoryNode)
    """
    cfg = config or AMMConfig()

    amms = []
    for spec in specs:
        amm_objects = generate_amm_objects(spec, ledger_seq=cfg.ledger_seq)
        amms.append(amm_objects)

    return amms
