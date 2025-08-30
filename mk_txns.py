#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests<3",
# ]
# ///
import json
import platform
import sys
import time
from random import randint

import requests
from types import SimpleNamespace as sn
default_rippled_rpc_port = "5005"
rippled_container = "rippled"

genesis_account =sn(address= "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh", seed="snoPBrXtMeMyMHUVTgbuqAfg1SUTb")
test_fund_account =sn(address="rh1HPuRVsYYvThxG2Bs1MfjmrVC73S16Fb", seed="snRzwEoNTReyuvz6Fb1CDXcaJUQdp")
fund_account = test_fund_account

initial_amount = str(99_999_999_990_000000)  # All of it minus the reserve for account 0
initial_amount = str(900_000_000_000000)
# 99999999900000000
# 999999990
# 1000000000
# 999_999_999908
constant_amount = str(10_000000)
#  account_info_pl = {"method": "account_info", "params": [{"account": genesis_account.address}]}
#  account_info_pl = {"method": "account_info", "params": [{"account": test_fund_account.address}]}
# result = requests.post(url, json=account_info_pl).json()
# print(json.dumps(result["result"]["account_data"], indent=2))
# host = "localhost" if platform.system() == "Darwin" else "172.20.0.2"
# ga 98999900000000998
# ga 989999000000
# 99999990
# tf 1000099999999000
host = "localhost"
devnet_port = "51234"
devnet_host = "s.devnet.rippletest.net"
devnet_url = f"https://{devnet_host}:{devnet_port}"
local_port = default_rippled_rpc_port

local_host = "172.17.0.2"
local_url = f"http://{local_host}:{local_port}"
url = devnet_url
url = local_url
# import subprocess as s
# import requests as r
# pl = {"method": "wallet_propose"}
# o = s.run("docker exec rippled rippled --silent wallet_propose".split(), capture_output=True, text=True).stdout.strip(\
# )
# result = json.loads(o)
# account = result["result"]
# alice = sn(address=account["account_id"], seed=account["master_seed"])

def payment_payload(source, dest, seed, amount):
    return {
        "method": "submit",
        "params": [
            {
                "secret": seed,
                "tx_json": {
                    "TransactionType": "Payment",
                    "Account": source,
                    "Destination": dest,
                    # "Fee": 200,
                    "Amount": amount,
                },
            },
        ],
    }


def initialize():
    source = genesis_account.address
    seed = genesis_account.seed
    destination = fund_account.address
    amount = initial_amount
  #   "rHz6DCjw6B7F3QKnUXUutKq5bxCLKJghHr",
  #   "snsNcauLW8i6bgeuYGbT7RN7EmG2d"
  #   "rLUC3iekQMydwL5xwv4Um2UVDLDP3oUCMZ",
  #   "spicmiKZ8x8zBHTNNUuGxe62VomCY"
  #   "rLVzTs7fSGStZ9a5KKQZkaH8gGfZW8taX3",
  #   "shthQ2oDVgeh82NatSPb9LKC3JVu9"
    # source = "rBuzwZcJRArXLVTFWPEJGTMeFECBYvpAFy"
    # seed = "ssK3VjRegtAYmgMyKGUKKFNFCQEN7"
    # destination = "ssK3VjRegtAYmgMyKGUKKFNFCQEN7"
    # destination = "rHJn8g6SjfZMZFzFNzgxRxzhECjWL1KCVs"
    # amount = "666000000"

    print(f"Using {url} with account {genesis_account.address} to send {amount} to {destination}")
    response = requests.post(url, json=payment_payload(source, destination, seed, amount), timeout=3)
    result = response.json()["result"]
    print(json.dumps(result, indent=2))

def constant():
    while True:
        amount = str(int(constant_amount) * randint(1, 3) + randint(1, 20)) #+  randint(1, 2) * randint(4, 6))
        # print(int(amount))
        print(int(amount)//int(1e6))
        response = requests.post(url, json=payment_payload(fund_account.address, genesis_account.address, fund_account.seed, amount), timeout=3)
        s = 0.05 * randint(1, 5)
        time.sleep(s)


if __name__ == "__main__":
    constant() if len(sys.argv) > 1 and sys.argv[1] in ["c", "const", "constant"] else initialize()
"""
## Current devnet
An typical transaction on devnet costs 1 drop and the reserve is 1 XRP
base fee = 1 drop
base reserve 1000000 drops = 1 XRP
1000000
999999 won't create an account but 1000000 will
incremental reserve 200000 drop = 0.2 XRP
# server_state
  "validated_ledger": {
    "base_fee": 1,
    "close_time": 802649951,
    "hash": "D54CEF3501BDFB55CC5A7B807B8DA4508B9B8C4650ECEDC068C38AC133639A1F",
    "reserve_base": 1000000,
    "reserve_inc": 200000,
    "seq": 3450463
  },
# fee
{
  "current_ledger_size": "0",
  "current_queue_size": "0",
  "drops": {
    "base_fee": "1",
    "median_fee": "500",
    "minimum_fee": "1",
    "open_ledger_fee": "1"
  },
  "expected_ledger_size": "522",
  "ledger_current_index": 3450473,
  "levels": {
    "median_level": "128000",
    "minimum_level": "256",
    "open_ledger_level": "256",
    "reference_level": "256"
  },
  "max_queue_size": "10440",
  "status": "success"
}
"""
