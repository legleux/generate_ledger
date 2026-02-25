import importlib.resources
from importlib.metadata import PackageNotFoundError, metadata, packages_distributions, version

fallback_version = "0.0.0+dev"
_top_pkg = __name__.split(".", 1)[0]

try:
    _dist = next(iter(packages_distributions().get(_top_pkg, [])))
except Exception:
    _dist = None

if _dist:
    try:
        __version__ = version(_dist)
    except PackageNotFoundError:
        __version__ = fallback_version
    try:
        __app_name__ = metadata(_dist).get("Name", _dist)
    except PackageNotFoundError:
        __app_name__ = _dist
else:
    __version__ = fallback_version
    __app_name__ = _top_pkg


# Get a pathlib.Path to the *root* of the package
root = importlib.resources.files(__app_name__)
data_dir = root / "data"
