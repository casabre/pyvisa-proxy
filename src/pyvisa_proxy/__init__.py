"""PyVISA extension in order to deal with remote 'local' hardware.

:copyright: 2022 by PyVISA-proxy Authors, see AUTHORS for more details.
:license: MIT, see LICENSE for more details.
"""

from .__main__ import main  # noqa
from .highlevel import ProxyVisaLibrary
from .ProxyServer import ProxyServer
from .version import get_version

__version__ = get_version()
__all__ = ["__version__", "ProxyServer"]

WRAPPER_CLASS = ProxyVisaLibrary
