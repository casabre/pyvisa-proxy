import sys

if sys.version_info >= (3, 8):
    from importlib.metadata import PackageNotFoundError, version
else:
    from importlib_metadata import PackageNotFoundError, version  # type: ignore

__version__ = "unknown"
try:
    __version__ = version(__name__)
except PackageNotFoundError:
    # package is not installed
    pass

from .RemoteClient import RemoteClient
from .RemoteServer import RemoteServer

__all__ = [
    '__version__',
    'RemoteClient',
    'RemoteServer'
]
