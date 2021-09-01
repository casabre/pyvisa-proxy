from importlib.metadata import version, PackageNotFoundError
from .PyVisaRemoteClient import PyVisaRemoteClient
from .PyVisaRemoteServer import PyVisaRemoteServer

__all__ = [
    '__version__',
    'PyVisaRemoteClient',
    'PyVisaRemoteServer'
]

try:
    __version__ = version("pyvisa.remote")
except PackageNotFoundError:
    # package is not installed
    pass
