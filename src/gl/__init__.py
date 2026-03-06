import importlib

_pkg = importlib.import_module("generate_ledger")

__path__ = _pkg.__path__  # type: ignore[attr-defined]


def __getattr__(name: str):
    return getattr(_pkg, name)


def __dir__():
    return sorted(set(dir(_pkg)))


__all__: list[str] = list(getattr(_pkg, "__all__", []))
