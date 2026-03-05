"""Tests for the develop/ package registry and graceful ImportError handling."""

import pytest


class TestDevelopRegistry:
    def test_import_succeeds(self):
        """The develop package should be importable on this branch."""
        from gl.develop import get_develop_builders
        assert callable(get_develop_builders)

    def test_returns_dict(self):
        from gl.develop import get_develop_builders
        builders = get_develop_builders()
        assert isinstance(builders, dict)

    def test_mpt_builder_registered(self):
        """MPT builder should now be registered (MPTokensV1 implemented)."""
        from gl.develop import get_develop_builders
        builders = get_develop_builders()
        assert "mpt" in builders
        assert callable(builders["mpt"]["builder"])
        assert builders["mpt"]["required_amendment"] == "MPTokensV1"

    def test_modules_importable(self):
        """Developed modules should be importable."""
        from gl.develop import mpt, vault
        assert hasattr(mpt, "generate_mpt_objects")
        assert hasattr(vault, "generate_vault_objects")

    def test_mpt_builder_callable(self):
        """MPT builder accepts accounts/config kwargs and returns a list."""
        from gl.develop.mpt import generate_mpt_objects
        from gl.ledger import LedgerConfig
        cfg = LedgerConfig(mpt_issuances=[])
        result = generate_mpt_objects(accounts=[], config=cfg)
        assert result == []

    def test_vault_stub_raises_not_implemented(self):
        from gl.develop.vault import generate_vault_objects
        with pytest.raises(NotImplementedError):
            generate_vault_objects(accounts=[], config=None)


class TestGracefulImportError:
    def test_gen_ledger_state_works_without_develop(self, monkeypatch):
        """gen_ledger_state() should work even if gl.develop import fails.

        We simulate this by temporarily making the import raise ImportError.
        """
        import sys

        # Save original module if present
        orig = sys.modules.get("gl.develop")

        # Force ImportError for gl.develop
        sys.modules["gl.develop"] = None  # type: ignore[assignment]
        try:
            from gl.ledger import LedgerConfig, gen_ledger_state
            cfg = LedgerConfig(
                account_cfg={"num_accounts": 2},
                base_dir="/tmp/test_graceful_import",
            )
            ledger = gen_ledger_state(cfg)
            assert "ledger" in ledger
            assert "accountState" in ledger["ledger"]
        finally:
            # Restore
            if orig is not None:
                sys.modules["gl.develop"] = orig
            else:
                sys.modules.pop("gl.develop", None)
