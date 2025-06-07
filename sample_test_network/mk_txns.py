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

import requests

default_rippled_rpc_port = "5005"
rippled_container = "rippled"
src_addr, src_seed = "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh", "snoPBrXtMeMyMHUVTgbuqAfg1SUTb"
dst_addr, dst_seed = "rh1HPuRVsYYvThxG2Bs1MfjmrVC73S16Fb", "snRzwEoNTReyuvz6Fb1CDXcaJUQdp"
initial_amount = str(99_999_999_990_000000)  # All of it minus the reserve for account 0
initial_amount = str(99_999_999_900_000000)
constant_amount = str(10_000000)

# host = "localhost" if platform.system() == "Darwin" else "172.20.0.2"
host = "localhost"
url = f"http://{host}:{default_rippled_rpc_port}"


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
                    "Amount": amount,
                },
            },
        ],
    }


def initialize():
    print(f"Using {url} with account {src_addr} to send {initial_amount} to {dst_addr}")
    response = requests.post(url, json=payment_payload(src_addr, dst_addr, src_seed, initial_amount), timeout=3)
    result = response.json()["result"]
    print(json.dumps(result, indent=2))

from random import randint
def constant():
    while True:
        amount = str(int(constant_amount) * randint(1, 3) + randint(1, 20)) #+  randint(1, 2) * randint(4, 6))
        # print(int(amount))
        print(int(amount)//int(1e6))
        response = requests.post(url, json=payment_payload(dst_addr, src_addr, dst_seed, amount), timeout=3)
        s = 0.05 * randint(1, 5)
        time.sleep(s)


if __name__ == "__main__":
    constant() if len(sys.argv) > 1 and sys.argv[1] in ["c", "const", "constant"] else initialize()
