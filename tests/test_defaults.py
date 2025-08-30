def test_defaults(test_config):
    assert test_config.algo in {"ed25519", "secp256k1"}
    assert test_config.network in {"mainnet", "testnet", "devnet"}
    assert isinstance(test_config.seed_length, int)
    assert test_config.key_encoding in {"hex", "base58", "bech32"}


# # Tests the cli override-ability
# def test_override_cli(test_config):
#     assert test_config.algo == "secp256k1"
