import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
import xrpl

import base58
import httpx
import xrpl.constants

"""
If the XRPFees Amendment is enabled (which it should be)
then `FeeSettings` ledger entry type. Replaces BaseFee, ReferenceFeeUnits, ReserveBase, and ReserveIncrement fields with BaseFeeDrops, ReserveBaseDrops, and ReserveIncrementDrops.
Updates the FeeSettings ledger entry type. Replaces BaseFee, ReferenceFeeUnits, ReserveBase, and ReserveIncrement fields with BaseFeeDrops, ReserveBaseDrops, and ReserveIncrementDrops.
BaseFee -> BaseFeeDrops
ReferenceFeeUnits -> BaseFeeDrops?
ReserveBase -> ReserveBaseDrops
ReserveIncrement -> ReserveIncrementDrops
"""

url = "http://localhost:5005"
# url = "http://172.20.0.6:5005"
devnet_url = "https://s.devnet.rippletest.net:51234"
# devnet_url = url

wallet_propose = {"method": "wallet_propose"}
accounts = []
default_balance = 100_000_000000  # 100k XRP
NUM_ACCOUNTS = 10
ACCOUNTS_FILE = accounts_info_file = Path("accounts.json")
ledger_template_file = Path("ledger_template.json")
ledger_file_json = Path("ledger.json")

amendments = Path("amendments.json")


@dataclass
class Amendment:
    name: str
    index: str
    enabled: bool
    obsolete: bool


def read_amendments_from_network(network: str = devnet_url):
    feature_response = httpx.post(devnet_url, json={"method": "feature"})
    result = feature_response.json()['result']
    amendments = result["features"]
    amendment_list = []
    for amendment_hash, info in amendments.items():
        name = info["name"]
        supported = info["supported"]
        amendment_list.append(
            Amendment(
                name=info["name"],
                index=amendment_hash,
                enabled=info["enabled"],
                obsolete=info.get("obsolete", False),
            )
        )
    return amendment_list


def compute_account_index(account_id: str) -> str:
    account_space_key = "0061"  # 0x0061
    # hashlib.sha512(message).digest()[:32]
    account_id_hex = base58.b58decode_check(account_id, alphabet=base58.XRP_ALPHABET)[1:].hex().upper()
    message = hashlib.sha512(bytes.fromhex(account_space_key + account_id_hex))
    account_index = message.digest()[:32].hex().upper()
    return account_index

wallet = xrpl.wallet.Wallet.from_seed(seed=xrpl.core.keypairs.generate_seed())

account_root_json = {
    # "Account": "",
    #"index": comput_account_index(account_id),
    "Balance": str(default_balance),
    "Flags": 0,
    "LedgerEntryType": "AccountRoot",
    "OwnerCount": 0,
    "PreviousTxnID": "32366162368956912E817EAD0710F10C0CF16432FC4C9E098D8A7BA4FD5DC0F0",
    "PreviousTxnLgrSeq": 4,
    "Sequence": 5,
}
account_roots = []


def generate_accounts_file(num_accounts: int = NUM_ACCOUNTS):
    accounts = []
    for i in range(num_accounts):
        res = httpx.post(url, json=wallet_propose)
        result = res.json()
        address = result["result"]["account_id"]
        seed = result["result"]["master_seed"]
        # acccount_index = compute_account_index(address)
        accounts.append({"address": address, "seed": seed})
    with accounts_info_file.open("w", encoding="UTF-8") as a:
        json.dump(accounts, a, indent=2)


def read_accounts_from_file(accounts_file: os.PathLike = ACCOUNTS_FILE):
    with accounts_file.open(encoding="UTF-8") as a:
        accounts = json.load(a)
    return accounts


def generate_accounts_list(accounts):
    account_roots = []
    for account in accounts:
        address = account["address"]
        account_index = compute_account_index(address)
        account_roots.append({"Account": address, "index": account_index, **account_root_json})
    return account_roots

# TODO: Generate the fee settings
# def generate_fee_settings():
#             {
#           "BaseFee": "a",
#           "Flags": 0,
#           "LedgerEntryType": "FeeSettings",
#           "ReferenceFeeUnits": 10,
#           "ReserveBase": 11000000,
#           "ReserveIncrement": 3000000,
#           "index": "4BC50C9B0D8515D3EAAE1E74B29A95804346C491EE1A95BF25E4AAB854A6A651"
#         },

def generate_ledger_file():
    ledger = {
        "ledger": {
            "accepted": True,
            "accountState": [
                {
                    "Account": "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh",
                    "Balance": "999999999910",
                    "Flags": 0,
                    "LedgerEntryType": "AccountRoot",
                    "OwnerCount": 0,
                    "PreviousTxnID": "A92EF82C3C68F771927E3892A2F708F12CBD492EF68A860F042E4053C8EC6C8D",
                    "PreviousTxnLgrSeq": 3,
                    "Sequence": 4,
                    "index": "2B6AC232AA4C4BE41BF49D2459FA4A0347E1B543A4C92FCEE0821C0201E2E9A8"
                },
                {
                    "LedgerEntryType": "FeeSettings",
                    "BaseFeeDrops": 333,
                    "Flags": 0,
                    "ReserveBaseDrops": 2000000,
                    "ReserveIncrementDrops": 123456,
                    "index": "4BC50C9B0D8515D3EAAE1E74B29A95804346C491EE1A95BF25E4AAB854A6A651"
                },
                {
                    "Amendments": [
                        "00C1FC4A53E60AB02C864641002B3172F38677E29C26C5406685179B37E1EDAC",
                        "03BDC0099C4E14163ADA272C1B6F6FABB448CC3E51F522F978041E4B57D9158C",
                        "12523DF04B553A0B1AD74F42DDB741DE8DC06A03FC089A0EF197E2A87F1D8107",
                        "138B968F25822EFBF54C00F97031221C47B1EAB8321D93C7C2AEAF85F04EC5DF",
                        "157D2D480E006395B76F948E3E07A45A05FE10230D88A7993C71F97AE4B1F2D1",
                        "15D61F0C6DB6A2F86BCF96F1E2444FEC54E705923339EC175BD3E517C8B3FF91",
                        "1CB67D082CF7D9102412D34258CEDB400E659352D3B207348889297A6D90F5EF",
                        "1E7ED950F2F13C4F8E2A54103B74D57D5D298FFDBD005936164EE9E6484C438C",
                        "1F4AFA8FA1BC8827AD4C0F682C03A8B671DCDF6B5C4DE36D44243A684103EF88",
                        "25BA44241B3BD880770BFA4DA21C7180576831855368CBEC6A3154FDE4A7676E",
                        "27CD95EE8E1E5A537FF2F89B6CEB7C622E78E9374EBD7DCBEDFAE21CD6F16E0A",
                        "2BF037D90E1B676B17592A8AF55E88DB465398B4B597AE46EECEE1399AB05699",
                        "2CD5286D8D687E98B41102BDD797198E81EA41DF7BD104E6561FEB104EFF2561",
                        "2E2FB9CF8A44EB80F4694D38AADAE9B8B7ADAFD2F092E10068E61C98C4F092B0",
                        "3012E8230864E95A58C60FD61430D7E1B4D3353195F2981DC12B0C7C0950FFAC",
                        "30CD365592B8EE40489BA01AE2F7555CAC9C983145871DC82A42A31CF5BAE7D9",
                        "31E0DA76FB8FB527CADCDF0E61CB9C94120966328EFA9DCA202135BAF319C0BA",
                        "32A122F1352A4C7B3A6D790362CC34749C5E57FCE896377BFDC6CCD14F6CD627",
                        "3318EA0CF0755AF15DAC19F2B5C5BCBFF4B78BDD57609ACCAABE2C41309B051A",
                        "35291ADD2D79EB6991343BDA0912269C817D0F094B02226C1C14AD2858962ED4",
                        "3CBC5C4E630A1B82380295CDA84B32B49DD066602E74E39B85EF64137FA65194",
                        "452F5906C46D46F407883344BFDD90E672B672C5E9943DB4891E3A34FEEEB9DB",
                        "47C3002ABA31628447E8E9A8B315FAA935CE30183F9A9B86845E469CA2CDC3DF",
                        "4F46DF03559967AC60F2EB272FEFE3928A7594A45FF774B87A7E540DB0F8F068",
                        "56B241D7A43D40354D02A9DC4C8DF5C7A1F930D92A9035C4E12291B3CA3E1C2B",
                        "586480873651E106F1D6339B0C4A8945BA705A777F3F4524626FF1FC07EFE41D",
                        "58BE9B5968C4DA7C59BA900961828B113E5490699B21877DEF9A31E9D0FE5D5F",
                        "5D08145F0A4983F23AFFFF514E83FAD355C5ABFBB6CAB76FB5BC8519FF5F33BE",
                        "621A0B264970359869E3C0363A899909AAB7A887C8B73519E4ECF952D33258A8",
                        "677E401A423E3708363A36BA8B3A7D019D21AC5ABD00387BDBEA6BDE4C91247E",
                        "67A34F2CF55BFC0F93AACD5B281413176FEE195269FA6D95219A2DF738671172",
                        "7117E2EC2DBF119CA55181D69819F1999ECEE1A0225A7FD2B9ED47940968479C",
                        "726F944886BCDF7433203787E93DD9AA87FAB74DFE3AF4785BA03BEFC97ADA1F",
                        "73761231F7F3D94EC3D8C63D91BDD0D89045C6F71B917D1925C01253515A6669",
                        "740352F2412A9909880C23A559FCECEDA3BE2126FED62FC7660D628A06927F11",
                        "755C971C29971C9F20C6F080F2ED96F87884E40AD19554A5EBECDCEC8A1F77FE",
                        "75A7E01C505DD5A179DFE3E000A9B6F1EDDEB55A12F95579A23E15B15DC8BE5A",
                        "763C37B352BE8C7A04E810F8E462644C45AFEAD624BF3894A08E5C917CF9FF39",
                        "7BB62DC13EC72B775091E9C71BF8CF97E122647693B50C5E87A80DFD6FCFAC50",
                        "7CA70A7674A26FA517412858659EBC7EDEEF7D2D608824464E6FDEFD06854E14",
                        "83FD6594FF83C1D105BD2B41D7E242D86ECB4A8220BD9AF4DA35CB0F69E39B2A",
                        "89308AF3B8B10B7192C4E613E1D2E4D9BA64B2EE2D5232402AE82A6A7220D953",
                        "894646DD5284E97DECFE6674A6D6152686791C4A95F8C132CCA9BAF9E5812FB6",
                        "8CC0774A3BF66D1D22E76BBDA8E8A232E6B6313834301B3B23E8601196AE6455",
                        "8EC4304A06AF03BE953EA6EDA494864F6F3F30AA002BABA35869FBB8C6AE5D52",
                        "8F81B066ED20DAECA20DF57187767685EEF3980B228E0667A650BAF24426D3B4",
                        "9196110C23EA879B4229E51C286180C7D02166DA712559F634372F5264D0EC59",
                        "93E516234E35E08CA689FA33A6D38E103881F8DCB53023F728C307AA89D515A7",
                        "950AE2EA4654E47F04AA8739C0B214E242097E802FD372D24047A89AB1F5EC38",
                        "955DF3FA5891195A9DAEFA1DDC6BB244B545DDE1BAA84CBB25D5F12A8DA68A0C",
                        "96FD2F293A519AE1DB6F8BED23E4AD9119342DA7CB6BAFD00953D16C54205D8B",
                        "98DECF327BF79997AEC178323AD51A830E457BFC6D454DAF3E46E5EC42DC619F",
                        "A730EB18A9D4BB52502C898589558B4CCEB4BE10044500EE5581137A2E80E849",
                        "AE35ABDEFBDE520372B31C957020B34A7A4A9DC3115A69803A44016477C84D6E",
                        "AE6AB9028EEB7299EBB03C7CBCC3F2A4F5FBE00EA28B8223AA3118A0B436C1C5",
                        "AF8DF7465C338AE64B1E937D6C8DA138C0D63AD5134A68792BBBE1F63356C422",
                        "B2A4DB846F0891BF2C76AB2F2ACC8F5B4EC64437135C6E56F3F859DE5FFD5856",
                        "B32752F7DCC41FB86534118FC4EEC8F56E7BD0A7DB60FD73F93F257233C08E3A",
                        "B4E4F5D2D6FB84DF7399960A732309C9FD530EAE5941838160042833625A6076",
                        "B6B3EEDC0267AB50491FDC450A398AF30DBCD977CECED8BEF2499CAB5DAC19E2",
                        "C1CE18F2A268E6A849C27B3DE485006771B4C01B2FCEC4F18356FE92ECD6BB74",
                        "C393B3AEEBF575E475F0C60D5E4241B2070CC4D0EB6C4846B1A07508FAEFC485",
                        "C4483A1896170C66C098DEA5B0E024309C60DC960DE5F01CD7AF986AA3D9AD37",
                        "C7981B764EC4439123A86CC7CCBA436E9B3FF73B3F10A0AE51882E404522FC41",
                        "C98D98EE9616ACD36E81FDEB8D41D349BF5F1B41DD64A0ABC1FE9AA5EA267E9C",
                        "CA7C02118BA27599528543DFE77BA6838D1B0F43B447D4D7F53523CE6A0E9AC2",
                        "D3456A862DC07E382827981CA02E21946E641877F19B8889031CC57FDCAC83E2",
                        "DAF3A6EB04FA5DC51E8E4F23E9B7022B693EFA636F23F22664746C77B5786B23",
                        "DB432C3A09D9D5DFC7859F39AE5FF767ABC59AED0A9FB441E83B814D8946C109",
                        "DF8B4536989BDACE3F934F29423848B9F1D76D09BE6A1FCFE7E7F06AA26ABEAD",
                        "EE3CF852F0506782D05E65D49E5DCC3D16D50898CD1B646BAE274863401CC3CE",
                        "F1ED6B4A411D8B872E65B9DCB4C8B100375B0DD3D62D07192E011D6D7F339013",
                        "F64E1EABBE79D55B3BB82020516CEC2C582A98A6BFE20FBE9BB6A0D233418064",
                        "FBD513F1B893AC765B78F250E6FFA6A11B573209D1842ADC787C850696741288"
                    ],
                    "Flags": 0,
                    "LedgerEntryType": "Amendments",
                    "index": "7DB0788C020F02780A673DC74757F23823FA3014C1866E72CC4CD8B226CD6EF4"
                },
            ],
            # "account_hash": "5DF3A98772FB73E782B8740E87885C6BAD9BA486422E3626DEF968AD2CB2C514",
            # "close_flags": 0,
            # "close_time": 733708800,
            # "close_time_human": "2023-Apr-02 00:00:00.000000",
            "close_time_resolution": 10,
            "closed": True,
            # "hash": "56DA0940767AC2F17F0E384F04816002403D0756432B9D503DDA20128A2AAF11",
            # "ledger_hash": "56DA0940767AC2F17F0E384F04816002403D0756432B9D503DDA20128A2AAF11",
            "ledger_index": "1",
            # "parent_close_time": 733708800,
            # "parent_hash": "56DA0940767AC2F17F0E384F04816002403D0756432B9D503DDA20128A2AAF11",
            "seqNum": "1",
            "totalCoins": "100000000000000000",
            "total_coins": "100000000000000000",
            # "transaction_hash": "9A77D1D1A4B36DA77B9C4DC63FDEB8F821741D157802F9C42A6ED86003D8B4A0",
            # "transactions": []
        },
        # "ledger_current_index": 1,
        # "status": "success",
        # "validated": True,
    }
    # for a in accounts:
    #     new_account_state.append(a)
    ledger_file = Path("sample_test_network/ledger.json")
    ledger_file.write_text(json.dumps(ledger, indent=2))




# for i in range(num_accounts):
#     res = httpx.post(url, json=wallet_propose)
#     result  = res.json()
#     address = result["result"]["account_id"]
#     seed = result["result"]["master_seed"]
#     acccount_index = compute_account_index(address)
#     accounts.append({"address": address, "seed": seed})
#     account_roots.append({"Account": address, "index": acccount_index, **account_root_json})

## Generate accounts
# generate_accounts_file()
# accounts = read_accounts_from_file(ACCOUNTS_FILE)
# accounts_json = generate_accounts_list(accounts)
## Handle amendments
amendments = [a.index for a in read_amendments_from_network() if a.enabled]
# for a in amendments:
    # print(a)
# accounts =
generate_ledger_file()
# print(json.dumps(account_roots))
