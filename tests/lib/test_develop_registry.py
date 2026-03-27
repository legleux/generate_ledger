"""Tests for the develop/ package registry and graceful ImportError handling."""

import pytest


class TestDevelopRegistry:
    def test_import_succeeds(self):
        """The develop package should be importable on this branch."""
        from generate_ledger.develop import get_develop_builders

        assert callable(get_develop_builders)

    def test_returns_dict(self):
        from generate_ledger.develop import get_develop_builders

        builders = get_develop_builders()
        assert isinstance(builders, dict)

    def test_no_active_builders(self):
        """All develop builders are currently commented out (MPT promoted, vault not implemented)."""
        from generate_ledger.develop import get_develop_builders

        builders = get_develop_builders()
        assert len(builders) == 0

    def test_vault_module_importable(self):
        """Vault module should be importable even though it raises NotImplementedError."""
        from generate_ledger.develop import vault

        assert hasattr(vault, "generate_vault_objects")

    def test_vault_stub_raises_not_implemented(self):
        from generate_ledger.develop.vault import generate_vault_objects

        with pytest.raises(NotImplementedError):
            generate_vault_objects(accounts=[], config=None)


class TestGracefulImportError:
    def test_gen_ledger_state_works_without_develop(self, monkeypatch):
        """gen_ledger_state() should work even if develop/ import fails."""
        import sys

        orig = sys.modules.get("generate_ledger.develop")

        sys.modules["generate_ledger.develop"] = None  # type: ignore[assignment]
        try:
            from generate_ledger.ledger import LedgerConfig, gen_ledger_state

            cfg = LedgerConfig(
                account_cfg={"num_accounts": 2},
                base_dir="/tmp/test_graceful_import",
            )
            ledger = gen_ledger_state(cfg)
            assert "ledger" in ledger
            assert "accountState" in ledger["ledger"]
        finally:
            if orig is not None:
                sys.modules["generate_ledger.develop"] = orig
            else:
                sys.modules.pop("generate_ledger.develop", None)
