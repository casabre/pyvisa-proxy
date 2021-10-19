"""
PyVISA extension in order to deal with remote 'local' hardware
"""
import sys
from .remote_client import RemoteClient
from .remote_server import RemoteServer

if sys.version_info >= (3, 8):
    from importlib.metadata import PackageNotFoundError, version
else:
    from importlib_metadata import PackageNotFoundError, version

__version__ = "unknown"
try:
    __version__ = version(__name__)
except PackageNotFoundError:
    # package is not installed
    pass

__all__ = [
    '__version__',
    'RemoteClient',
    'RemoteServer'
]
