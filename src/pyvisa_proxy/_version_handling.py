"""Retrieve version of package.

:copyright: 2022 by PyVISA-proxy Authors, see AUTHORS for more details.
:license: MIT, see LICENSE for more details.
"""

from importlib.metadata import PackageNotFoundError, version


def get_version():
    """Retrieve the package version."""
    try:
        return version(__package__)
    except PackageNotFoundError:
        # package is not installed
        return "unknown"
