"""Tests for generate_ledger.services.compose_service."""

from gl.services.compose_service import load_compose_config


class TestLoadComposeConfig:
    def test_defaults(self):
        cfg = load_compose_config()
        assert cfg.num_validators == 5
        assert cfg.validator_name == "val"

    def test_profile_overrides(self):
        cfg = load_compose_config(profile_doc={"num_validators": 10})
        assert cfg.num_validators == 10

    def test_cli_overrides_win(self):
        cfg = load_compose_config(
            profile_doc={"num_validators": 10},
            overrides={"num_validators": 3},
        )
        assert cfg.num_validators == 3
