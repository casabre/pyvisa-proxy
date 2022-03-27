import sys

if sys.version_info >= (3, 8):
    from importlib.metadata import PackageNotFoundError, version
else:
    from importlib_metadata import PackageNotFoundError, version


def get_version():
    try:
        return version("pyvisa-proxy")
    except PackageNotFoundError:
        # package is not installed
        return "unknown"
