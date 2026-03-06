#!/usr/bin/env python3
"""Generate a 10k-account ledger with 4 gateways and full trustline coverage.

Each gateway issues one currency. Every non-gateway account trusts all 4 gateways.
Trustline objects are built directly (no transaction signing) for speed.

Usage:
    uv run scripts/gen_gateway_ledger.py
    uv run scripts/gen_gateway_ledger.py --accounts 5000 --output /tmp/my_ledger
"""

import argparse
import json
import time
from pathlib import Path

from generate_ledger import ledger_builder
from gl.accounts import AccountConfig, generate_accounts, write_accounts_json
from gl.amendments import get_enabled_amendment_hashes
from gl.crypto import sha512_half
from gl.indices import owner_dir, ripple_state_index
from gl.ledger import FeeConfig
from gl.trustlines import TrustlineObjects


def build_trustline_objects(
    gateway_address: str,
    account_address: str,
    currency: str,
    limit: str = "100000000000",
    ledger_seq: int = 2,
) -> TrustlineObjects:
    """Build trustline objects directly — no transaction signing."""
    rsi = ripple_state_index(gateway_address, account_address, currency)

    # Determine high/low ordering
    if gateway_address.encode() < account_address.encode():
        lo_addr, hi_addr = gateway_address, account_address
    else:
        lo_addr, hi_addr = account_address, gateway_address

    # Deterministic PreviousTxnID (hash of the index — unique per trustline)
    txn_id = sha512_half(rsi.encode()).hex().upper()

    ripple_state = {
        "Balance": {"currency": currency, "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji", "value": "0"},
        "Flags": 131072,
        "HighLimit": {"currency": currency, "issuer": hi_addr, "value": limit},
        "HighNode": "0",
        "LedgerEntryType": "RippleState",
        "LowLimit": {"currency": currency, "issuer": lo_addr, "value": limit},
        "LowNode": "0",
        "PreviousTxnID": txn_id,
        "PreviousTxnLgrSeq": ledger_seq,
        "index": rsi,
    }

    root_a = owner_dir(gateway_address)
    dir_a = {
        "Flags": 0,
        "Indexes": [rsi],
        "LedgerEntryType": "DirectoryNode",
        "Owner": gateway_address,
        "PreviousTxnID": txn_id,
        "PreviousTxnLgrSeq": ledger_seq,
        "RootIndex": root_a,
        "index": root_a,
    }
    root_b = owner_dir(account_address)
    dir_b = {
        "Flags": 0,
        "Indexes": [rsi],
        "LedgerEntryType": "DirectoryNode",
        "Owner": account_address,
        "PreviousTxnID": txn_id,
        "PreviousTxnLgrSeq": ledger_seq,
        "RootIndex": root_b,
        "index": root_b,
    }

    return TrustlineObjects(ripple_state, dir_a, dir_b)


def main():
    parser = argparse.ArgumentParser(description="Generate gateway ledger with full trustline coverage")
    parser.add_argument("-n", "--accounts", type=int, default=10_000, help="Total accounts (default: 10000)")
    parser.add_argument("-g", "--gateways", type=int, default=4, help="Number of gateways (default: 4)")
    parser.add_argument("-o", "--output", type=Path, default=Path("/tmp/test_gateways"), help="Output directory")
    parser.add_argument("--currencies", type=str, default="USD,EUR,GBP,JPY", help="Comma-separated currencies")
    parser.add_argument("--limit", type=str, default="100000000000", help="Trust limit (default: 100B)")
    args = parser.parse_args()

    currencies = [c.strip() for c in args.currencies.split(",")]
    if len(currencies) < args.gateways:
        # Cycle currencies if fewer than gateways
        currencies = (currencies * ((args.gateways // len(currencies)) + 1))[: args.gateways]

    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    total_start = time.perf_counter()

    # --- Step 1: Generate accounts ---
    t0 = time.perf_counter()
    accounts = generate_accounts(AccountConfig(num_accounts=args.accounts, algo="ed25519"))
    write_accounts_json(accounts, output_dir / "accounts.json")
    t1 = time.perf_counter()
    print(f"  Accounts:   {t1 - t0:.2f}s  ({args.accounts:,} accounts)")

    # --- Step 2: Build trustlines (fast path — no tx signing) ---
    t2 = time.perf_counter()
    trustline_objects: list[TrustlineObjects] = []
    for gw_idx in range(args.gateways):
        gateway = accounts[gw_idx]
        currency = currencies[gw_idx]
        for acct_idx in range(args.gateways, args.accounts):
            acct = accounts[acct_idx]
            tl = build_trustline_objects(gateway.address, acct.address, currency, args.limit)
            trustline_objects.append(tl)
    t3 = time.perf_counter()
    print(f"  Trustlines: {t3 - t2:.2f}s  ({len(trustline_objects):,} trustlines)")

    # --- Step 3: Assemble ledger ---
    t4 = time.perf_counter()
    fee_cfg = FeeConfig()
    amendment_hashes = get_enabled_amendment_hashes()
    gw_addresses = {accounts[i].address for i in range(args.gateways)}

    ledger = ledger_builder.assemble_ledger_json(
        accounts=accounts,
        fees=fee_cfg.xrpl,
        amendment_hashes=amendment_hashes,
        trustline_objects=trustline_objects,
        amm_issuers=gw_addresses,  # Sets lsfDefaultRipple on gateways
    )
    t5 = time.perf_counter()
    print(f"  Assembly:   {t5 - t4:.2f}s")

    # --- Step 4: Write ---
    t6 = time.perf_counter()
    output_file = output_dir / "ledger.json"
    with output_file.open("w") as f:
        json.dump(ledger, f)
    t7 = time.perf_counter()
    print(f"  Write:      {t7 - t6:.2f}s")

    total = time.perf_counter() - total_start
    size_mb = output_file.stat().st_size / 1024 / 1024
    num_objects = len(ledger["ledger"]["accountState"])

    print(f"\n{'=' * 50}")
    print(f"  Total time:      {total:.2f}s")
    print(f"  Accounts:        {args.accounts:,}")
    print(f"  Gateways:        {args.gateways} ({', '.join(currencies[: args.gateways])})")
    print(f"  Trustlines:      {len(trustline_objects):,}")
    print(f"  Ledger objects:  {num_objects:,}")
    print(f"  Output:          {output_file}")
    print(f"  File size:       {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
