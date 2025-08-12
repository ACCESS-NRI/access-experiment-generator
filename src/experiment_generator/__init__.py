"""
experiment_generator package.
"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("experiment_generator")
except PackageNotFoundError:
    # package is not installed
    pass
