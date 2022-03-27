"""
PyVISA extension in order to deal with remote 'local' hardware
"""

from .ProxyResource import ProxyResource
from .ProxyServer import ProxyServer
from .version import get_version

__version__ = get_version()
__all__ = ["__version__", "ProxyResource", "ProxyServer"]
