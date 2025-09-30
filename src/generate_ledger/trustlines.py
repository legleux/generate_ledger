import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from pydantic import PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict
from gl.indices import ripple_state_index
from generate_ledger import Wallet, generate_seed

from xrpl import CryptoAlgorithm

@dataclass
class Trustline:
    currency: str
    hi_address: str
    hi_amount: PositiveInt
    lo_address: str
    lo_amount: PositiveInt

class TrustlineConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GL_", env_file=".env")
    limit_amount: str = str(100e9 * 1e6)  # 100B XRP


def generate_trustline(hi, lo, currency, hi_amount, lo_amount):
    flags = 131072
    balance = {
        "currency": currency,
        "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",
        "value": "0",
    }
    high_limit = {
        "currency": currency,
        "issuer": hi,
        "value": hi_amount,
    }
    low_limit = {
        "currency": currency,
        "issuer": lo,
        "value": lo_amount,
    }
    trustline = dict(
        Balance=balance,
        Flags=flags,
        HighLimit=high_limit,
        HighNode="0",
        LedgerEntryType="RippleState",
        LowLimit=low_limit,
        LowNode="0",
        PreviousTxnID="72DC4832A16946423E1B29A971A98420D803FF24BA7309DC84F362AFBF84296F",
        PreviousTxnLgrSeq=404995,
        index=ripple_state_index(lo, hi, currency),
    )
    return trustline

# def generate_trustlines()
