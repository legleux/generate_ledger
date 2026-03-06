"""Tests for generate_ledger.config re-exports."""


def test_compose_config_importable():
    from generate_ledger.config import ComposeConfig

    assert ComposeConfig is not None


def test_ledger_config_importable():
    from generate_ledger.config import LedgerConfig

    assert LedgerConfig is not None


def test_all_list_correct():
    """__all__ should contain both names (not silently concatenated)."""
    from generate_ledger import config

    assert "ComposeConfig" in config.__all__
    assert "LedgerConfig" in config.__all__
    assert len(config.__all__) == 2
