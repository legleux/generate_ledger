"""Gateway topology trustline generation for scale benchmarking."""

import random
from dataclasses import dataclass

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from gl.accounts import Account
from gl.indices import owner_dir, ripple_state_index
from gl.trustlines import TrustlineObjects

DEFAULT_GATEWAY_CURRENCIES = [
    "USD", "EUR", "GBP", "JPY", "BTC", "ETH", "CNY", "MXN",
    "CAD", "AUD", "CHF", "KRW", "SGD", "HKD", "NOK", "SEK",
]


@dataclass
class GatewayAsset:
    """A single asset issued by a gateway."""

    gateway_index: int  # Index of the gateway in the accounts list
    currency: str


class GatewayConfig(BaseSettings):
    """Configuration for gateway topology trustline generation."""

    model_config = SettingsConfigDict(env_prefix="GL_GATEWAY_", env_file=".env")

    num_gateways: int = 0  # 0 = disabled
    assets_per_gateway: int = 4
    currencies: list[str] = Field(default_factory=lambda: list(DEFAULT_GATEWAY_CURRENCIES))
    coverage: float = 0.5  # Fraction of non-gateway accounts that get trustlines
    connectivity: float = 0.5  # Fraction of gateways each holder connects to
    default_limit: str = str(int(100e9))
    ledger_seq: int = 2
    seed: int | None = None  # RNG seed for reproducibility


def _build_gateway_assets(config: GatewayConfig) -> dict[int, list[str]]:
    """Build a mapping of gateway_index -> list of currency codes."""
    pool = config.currencies
    assets_by_gw: dict[int, list[str]] = {}
    for gw_idx in range(config.num_gateways):
        currencies = []
        for asset_idx in range(config.assets_per_gateway):
            flat_idx = gw_idx * config.assets_per_gateway + asset_idx
            currencies.append(pool[flat_idx % len(pool)])
        assets_by_gw[gw_idx] = currencies
    return assets_by_gw


def generate_trustline_objects_fast(
    account_a: Account,
    account_b: Account,
    currency: str,
    limit: int,
    ledger_seq: int = 2,
) -> TrustlineObjects:
    """Generate trustline objects without signing a TrustSet transaction.

    Uses the RippleState index as a synthetic PreviousTxnID.  This is valid
    for genesis ledgers — rippled does not validate PreviousTxnID on bootstrap.
    ~100x faster than generate_trustline_objects() because it skips
    Wallet.from_seed() and xrpl-py transaction signing.
    """
    rsi = ripple_state_index(account_a.address, account_b.address, currency)

    # Determine high/low accounts (lexicographic order of addresses)
    if account_a.address.encode() < account_b.address.encode():
        lo_address, hi_address = account_a.address, account_b.address
    else:
        lo_address, hi_address = account_b.address, account_a.address

    # Synthetic PreviousTxnID: the RSI itself (deterministic, unique per trustline)
    txn_id = rsi

    ripple_state = {
        "Balance": {
            "currency": currency,
            "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",
            "value": "0",
        },
        "Flags": 131072,  # lsfLowReserve
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


def generate_gateway_trustlines(
    accounts: list[Account],
    config: GatewayConfig,
) -> tuple[list[TrustlineObjects], set[str]]:
    """Generate trustlines for a gateway topology.

    The first ``config.num_gateways`` accounts are treated as gateways.
    A fraction (``config.coverage``) of the remaining accounts are selected
    to hold trustlines.  Each selected account connects to a fraction
    (``config.connectivity``) of the gateways, creating trustlines for ALL
    assets of each connected gateway.

    Returns:
        ``(trustline_objects, gateway_addresses)`` where *gateway_addresses*
        is the set of addresses that need ``lsfDefaultRipple``.
    """
    if config.num_gateways <= 0:
        return [], set()

    num_gw = config.num_gateways
    if len(accounts) <= num_gw:
        msg = f"Need more accounts ({len(accounts)}) than gateways ({num_gw})"
        raise ValueError(msg)

    rng = random.Random(config.seed)

    assets_by_gw = _build_gateway_assets(config)
    gateways = accounts[:num_gw]
    regular = accounts[num_gw:]

    # Select holders
    num_holders = max(1, int(len(regular) * config.coverage))
    holders = rng.sample(regular, min(num_holders, len(regular)))

    # How many gateways each holder connects to
    num_connected = max(1, round(num_gw * config.connectivity))
    gw_indices = list(range(num_gw))

    trustlines: list[TrustlineObjects] = []
    created: set[tuple[str, str, str]] = set()
    limit = int(config.default_limit)

    for holder in holders:
        connected = rng.sample(gw_indices, min(num_connected, num_gw))
        for gw_idx in connected:
            gateway = gateways[gw_idx]
            for currency in assets_by_gw[gw_idx]:
                pair_key = (*sorted([gateway.address, holder.address]), currency)
                if pair_key in created:
                    continue
                created.add(pair_key)

                tl = generate_trustline_objects_fast(
                    account_a=gateway,
                    account_b=holder,
                    currency=currency,
                    limit=limit,
                    ledger_seq=config.ledger_seq,
                )
                trustlines.append(tl)

    gateway_addresses = {gw.address for gw in gateways}
    return trustlines, gateway_addresses
