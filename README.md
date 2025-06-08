# generate_ledger

Generates an initial ledger state for a customized XRPL network.

Make sure to set this in the validators configs to maintain the state after a flag ledger!
[voting]
reference_fee = 1
account_reserve = 1000000
owner_reserve = 200000

TODO:
1. Ability to copy the settings (fee settings etc) from one of the live networks.
1. make the ledger.json a jinja template and filter out the fields that are unneeded.
1. Make it a python package.
1. Pre-generate other ledger objects besides accounts.
