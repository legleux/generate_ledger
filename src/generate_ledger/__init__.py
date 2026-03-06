import importlib.resources
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("generate-ledger")
except PackageNotFoundError:
    __version__ = "0.0.0+dev"

__app_name__ = "generate-ledger"

root = importlib.resources.files(__package__)
data_dir = root / "data"
