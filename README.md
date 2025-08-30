# generate_ledger

Generates an initial ledger state for a customizing XRPL network.

Be sure to set this in the validators configs to maintain the state after a flag ledger!

```ini
[voting]
reference_fee = 1
account_reserve = 1000000
owner_reserve = 200000
```

## TODO
- [ ] Unify configuration variables between modules.
- [ ] Ability to copy the settings (e.g. fee settings) from one of the live networks.
- [ ] Use a templated config for easier observation/modification.
- [ ] Pre-generate other ledger objects besides accounts.
  - [ ] Issued Currencies
  - [ ] AMM
  - [ ] MPT
- [x] Make it a python package.
