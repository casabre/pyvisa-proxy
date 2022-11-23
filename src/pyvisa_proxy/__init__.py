"""PyVISA extension in order to deal with remote 'local' hardware.

:copyright: 2022 by PyVISA-proxy Authors, see AUTHORS for more details.
:license: MIT, see LICENSE for more details.
"""

from ._main import main as run_server
from ._version_handling import get_version
from .highlevel import ProxyVisaLibrary
from .ProxyServer import ProxyServer

__version__ = get_version()
__all__ = ["__version__", "run_server", "ProxyServer"]

WRAPPER_CLASS = ProxyVisaLibrary
