import json
import random
from pathlib import Path

def generate_ledger(*, output: Path, accounts: int, seed: int | None) -> None:
    rnd = random.Random(seed)
    # NOTE: stub structure — replace with real XRPL-gen logic
    ledger = {
        "ledger": {
            "accountState": [
                {
                    "Account": f"r{rnd.getrandbits(160):040x}"[:34],
                    "Balance": str(1_000_000_000),
                    "Flags": 0,
                    "LedgerEntryType": "AccountRoot",
                    "OwnerCount": 0,
                    "Sequence": 1,
                }
                for _ in range(accounts)
            ]
        }
    }
    output.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
