from gl.compose import write_compose_file, ComposeConfig
from gl.ledger import write_ledger_file, LedgerConfig, FeeConfig
from gl.accounts import AccountConfig
from gl.rippled_cfg import RippledConfigSpec

fee_cfg = FeeConfig(
    base_fee_drops=123,
    reserve_base_drops=1_000_000,
    reserve_increment_drops=666,
)

compose_cfg = ComposeConfig()

currency_code = "USD"
account_cfg = AccountConfig(
    num_accounts = 20
)
# trustlines =
ledger_cfg  = LedgerConfig(
    account_cfg=account_cfg,
    fees_cfg=fee_cfg,
)
rippled_cfg = RippledConfigSpec(
    account_reserve=fee_cfg.reserve_base_drops,
    reference_fee=fee_cfg.base_fee_drops,
    owner_reserve=fee_cfg.reserve_increment_drops,
    )

write_compose_file()
write_ledger_file(config=ledger_cfg)
rippled_cfg.write()

# payment_payload = {"method": "feature"}
# trustset_payload = {"method": "feature"}
# payment_payload = {"method": "feature"}

# data = json.dumps(payload).encode("utf-8")
# response = urllib.request.urlopen(url, data=data, timeout=timeout)
# res = json.loads(response.read())
