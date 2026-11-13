from importlib.metadata import PackageNotFoundError, version

import matplotlib

# the report figures are drawn on the server, without a window
matplotlib.use("Agg")

try:
    __version__ = version("behavior-data-visualizer")
except PackageNotFoundError:
    # package is not installed
    pass
