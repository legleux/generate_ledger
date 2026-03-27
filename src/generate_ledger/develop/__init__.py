"""Pre-release (develop branch) ledger object registry.

This package contains ledger objects that are not yet enabled on mainnet.
On the ``main`` branch of this repository the entire ``develop/`` directory
may be absent, and the ``ImportError`` raised when importing this package
is caught gracefully in ``ledger.py:gen_ledger_state()``.

Each entry in ``_DEVELOP_OBJECTS`` maps a short name to:
  - module_path: dotted import path of the builder module
  - builder_function: name of the callable in that module
  - required_amendment: the XRPL amendment that must be enabled
"""

from __future__ import annotations

import importlib
from typing import Any

# Registry of pre-release object builders.
# Uncomment entries as implementations are added.
_DEVELOP_OBJECTS: list[tuple[str, str, str, str]] = [
    # (name, module_path, builder_function, required_amendment)
    # ("vault", "generate_ledger.develop.vault", "generate_vault_objects", "SingleAssetVault"),
]


def get_develop_builders() -> dict[str, dict[str, Any]]:
    """Return a dict of available develop-branch object builders.

    Each value is ``{"builder": <callable>, "required_amendment": <str>}``.
    Builders whose module cannot be imported are silently skipped.
    """
    builders: dict[str, dict[str, Any]] = {}
    for name, module_path, fn_name, amendment in _DEVELOP_OBJECTS:
        try:
            mod = importlib.import_module(module_path)
            fn = getattr(mod, fn_name)
            builders[name] = {
                "builder": fn,
                "required_amendment": amendment,
            }
        except (ImportError, AttributeError):
            continue
    return builders
