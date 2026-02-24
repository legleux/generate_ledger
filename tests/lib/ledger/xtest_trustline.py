from xrpl.wallet import Wallet
from xrpl import CryptoAlgorithm
from xrpl.core.keypairs import generate_seed
from xrpl.clients import JsonRpcClient
from xrpl.models.transactions import (
    AccountSet, AccountSetAsfFlag,
    Payment,
    TrustSet,
    )
from xrpl.transaction import submit_and_wait, submit
from xrpl.models.requests import AccountLines, LedgerData
from xrpl.models import IssuedCurrency

url = "http://172.20.0.2:5005" # val0
url = "http://172.20.0.4:5005" # rippled
client = JsonRpcClient(url=url)
algo=CryptoAlgorithm.SECP256K1
# val0    172.20.0.2
# val1    172.20.0.4
# val2    172.20.0.6
# val3    172.20.0.7
# val4    172.20.0.5
# rippled 172.20.0.3


accounts = [
  [
    "rLgKpfNbtPu4PhRZrj7oBtamAEyx6FFgjf",
    "ss817Ye3JAeNe1VnZiyp6KJWVBcDT"
  ],
  [
    "rsTtCJfwCTgrAkNcLH22g7TdMTKFGpi9QU",
    "spFh6NwCnTHHLuLr5vUdCWHj51sSQ"
  ]
]

alice = Wallet.from_seed(seed=accounts[0][1], algorithm=algo)
bob = Wallet.from_seed(seed=accounts[1][1], algorithm=algo)

code  = "USD"
limit = int(100e12)
payment = 1000
ic = IssuedCurrency(currency=code, issuer=alice.address)
ica_limit = ic.to_amount(value=limit)
ica_payment = ic.to_amount(value=payment)

# allow alice ious to ripple
#as_txn = AccountSet(account=alice.address, set_flag=AccountSetAsfFlag.ASF_DEFAULT_RIPPLE)
#submit_and_wait(transaction=as_txn, client=client, wallet=alice)

# allow bob to trust alice
ts_txn = TrustSet(
  account=bob.address,
  limit_amount=ica_limit,
  sequence=5,
  signing_pub_key=bob.public_key,
  fee="123",
)
ts_dict = dict(
  Account=bob.address,
  LimitAmount="100",
  Sequence=5,
  SigningPubKey=bob.public_key,
  Fee="123",
)
# submit_and_wait(transaction=ts_txn, client=client, wallet=bob)
signing_payload_hex = encode_for_signing(ts_txn.to_xrpl())
signing_payload_hex = encode_for_signing(ts_dict)
signed_ts_txn = sign(signing_payload_hex, bob.private_key)
# signature_hex = sign(bytes.fromhex(signing_payload_hex), bob.private_key)
response = submit(signed_ts_txn, client=client)

response = submit(transaction=ts_txn, client=client)
# txn_id=="953678973935AF3A74058814C8F08654B9508B1D9E432656CFDC055901424DC6"
# send ious from alice -> bob
pmt_txn = Payment(account=alice.address, destination=bob.address, amount=ica_payment)
response = submit_and_wait(transaction=pmt_txn, client=client, wallet=alice)

ledger_data = client.request(LedgerData())
ignored_types = ("AccountRoot", "Amendments", "FeeSettings", "LedgerHashes")
nodes = [n for n in ledger_data.result["state"] if n["LedgerEntryType"] not in ignored_types]
directory_nodes = [n for n in ledger_data.result["state"] if n["LedgerEntryType"] == "DirectoryNode"]
trustlines = [n for n in ledger_data.result["state"] if n["LedgerEntryType"] == "RippleState"]

alr_a = AccountLines(account=alice.address, ledger_index="validated")
a_al = client.request(request=alr_a)
alr_b = AccountLines(account=bob.address, ledger_index="validated")
b_al = client.request(request=alr_b)
pass

### Needed
from xrpl.core.keypairs import sign
from xrpl.core.binarycodec import encode_for_signing
from binascii import unhexlify
import hashlib

# get the trustset txnid
from binascii import unhexlify
from xrpl.core.keypairs import sign
from xrpl.core import binarycodecMa
from xrpl.models.requests import SubmitOnly
from xrpl.ledger import get_latest_validated_ledger_sequence
from xrpl.core.binarycodec import encode, encode_for_signing
from xrpl.transaction import autofill, autofill_and_sign

# if needed...
# seq = get_latest_validated_ledger_sequence(client=client)
# last_ledger_sequence = seq + 100

ts_txn = TrustSet(
  account=bob.address,
  limit_amount=ica_limit,
  sequence=7,
  signing_pub_key=bob.public_key,
  fee="123",
)

TXN_PREFIX = bytes.fromhex("54584E00")  # "TXN\0"

signing_payload_hex = encode_for_signing(ts_txn.to_xrpl())
signature_hex = sign(bytes.fromhex(signing_payload_hex), bob.private_key)
signed_dict = {**ts_txn.to_xrpl(), "TxnSignature": signature_hex}
tx_blob = encode(signed_dict)
txn_id = _sha512_half(TXN_PREFIX + unhexlify(tx_blob)).hex().upper()
resp = client.request(SubmitOnly(tx_blob=tx_blob))
"""
To create the trustline, we need 3 ledger objects. 2 directory nodes for each side and the ripple_state
create 2 directory nodes for each side
indexes = [index_id of RippleState]
PreviousTxnID= of each DirectoryNode is a TrustSet Txn index ID
RootIndex is index
"""
# 1. Create the trustSet txn that would create the trustline to get the txn_id
ts_dict = dict(
  account=bob.address,
  limit_amount=ica_limit,
  sequence=4,
  signing_pub_key=bob.public_key,
  fee="123"
)

ts_txn = TrustSet(
  account=bob.address,
  limit_amount=ica_limit,
  sequence=4,
  signing_pub_key=bob.public_key,
  fee="123",
)
TXN_PREFIX = bytes.fromhex("54584E00")  # "TXN\0"
signing_payload_hex = encode_for_signing(ts_txn.to_xrpl())
signing_payload_hex = encode_for_signing(ts_dict)
# signing_payload_hex = encode_for_signing(TrustSet.from_dict(ts_dict))
signature_hex = sign(bytes.fromhex(signing_payload_hex), bob.private_key)
# signature_hex = sign(signing_payload_hex, bob.private_key)
# signed_dict = {**ts_txn.to_xrpl(), "TxnSignature": signature_hex}
#
## or maybe
ts_dict.update(txn_signature=signature_hex)
res = submit(TrustSet.from_dict(ts_dict), client)
txn_id = _sha512_half(TXN_PREFIX + unhexlify(tx_blob)).hex().upper()
# 2. Form the directoryNodes,
from gl.indices import ripple_state_index, owner_dir

rsi = ripple_state_index(alice.address, bob.address, code)
root_index_alice = owner_dir(alice.address)
root_index_bob = owner_dir(bob.address)
dn_1 = {
  "Flags": 0,
  "Indexes": [rsi],
  "LedgerEntryType": "DirectoryNode",
  "Owner": alice.address,
  "PreviousTxnID": txn_id,
  "PreviousTxnLgrSeq": 2,
  "RootIndex": root_index_alice,
  "index": root_index_alice
}
dn_2 = {
  "Flags": 0,
  "Indexes": [rsi],
  "LedgerEntryType": "DirectoryNode",
  "Owner": bob.address,
  "PreviousTxnID": txn_id,
  "PreviousTxnLgrSeq": 2,
  "RootIndex": root_index_bob,
  "index": root_index_bob
}
directory_node_alice = dn_1
directory_node_bob = dn_2
trust_set_txn_id = txn_id
