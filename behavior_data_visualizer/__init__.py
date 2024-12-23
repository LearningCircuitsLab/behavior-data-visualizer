from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("behavior-data-visualizer")
except PackageNotFoundError:
    # package is not installed
    pass
