There are 3 objects required on ledger to describe a [Trustline](https://xrpl.org/docs/concepts/tokens/fungible-tokens#trust-lines).
1. `DirectoryNode` for side A

    {
        'Flags': 0, 
        'Indexes': ['56DF4E345380CD7EFF6A79F29B9413845A42263079CB74AC18E2AEB9414510E3'],
        'LedgerEntryType': 'DirectoryNode',
        'Owner': 'rLgKpfNbtPu4PhRZrj7oBtamAEyx6FFgjf',
        'PreviousTxnID': '953678973935AF3A74058814C8F08654B9508B1D9E432656CFDC055901424DC6',
        'PreviousTxnLgrSeq': 2,
        'RootIndex': '628E72007CB81AE478E3F5D6E10840C024D249AF76D78F87CB258A6EB6505F31',
        'index': '628E72007CB81AE478E3F5D6E10840C024D249AF76D78F87CB258A6EB6505F31'
    }

1. `DirectoryNode` for side B

    {
        'Flags': 0, 
        'Indexes': ['56DF4E345380CD7EFF6A79F29B9413845A42263079CB74AC18E2AEB9414510E3'],
        'LedgerEntryType': 'DirectoryNode',
        'Owner': 'rsTtCJfwCTgrAkNcLH22g7TdMTKFGpi9QU',
        'PreviousTxnID': '953678973935AF3A74058814C8F08654B9508B1D9E432656CFDC055901424DC6',
        'PreviousTxnLgrSeq': 2,
        'RootIndex': '1F56D6D82FCE349EE70B8DFB9A423139E13DD8409473264A0A9840598424A71A',
        'index': '1F56D6D82FCE349EE70B8DFB9A423139E13DD8409473264A0A9840598424A71A'
}

1. `RippleState`

    {
      "Flags": 131072,
      "Balance": {
        "currency": "USD",
        "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",
        "value": "0"
      },
      "HighLimit": {
        "currency": "USD",
        "issuer": "rLgKpfNbtPu4PhRZrj7oBtamAEyx6FFgjf",
        "value": 100000000000000
      },
      "HighNode": "0",
      "LedgerEntryType": "RippleState",
      "LowLimit": {
        "currency": "USD",
        "issuer": "rsTtCJfwCTgrAkNcLH22g7TdMTKFGpi9QU",
        "value": 0
      },
      "LowNode": "0",
      "PreviousTxnID": "72DC4832A16946423E1B29A971A98420D803FF24BA7309DC84F362AFBF84296F",
      "PreviousTxnLgrSeq": 404995,
      "index": "56DF4E345380CD7EFF6A79F29B9413845A42263079CB74AC18E2AEB9414510E3"
    }
