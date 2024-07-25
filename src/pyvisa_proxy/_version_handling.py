"""Retrieve version of package.

:copyright: 2022 by PyVISA-proxy Authors, see AUTHORS for more details.
:license: MIT, see LICENSE for more details.
"""

import sys
from importlib.metadata import PackageNotFoundError, version


def get_version():
    """Retrieve the package version."""
    try:
        return version("pyvisa-proxy")
    except PackageNotFoundError:
        # package is not installed
        return "unknown"
