"""Run PyVISA-proxy server as service.

:copyright: 2022 by PyVISA-proxy Authors, see AUTHORS for more details.
:license: MIT, see LICENSE for more details.
"""
import argparse
import logging
import sys
import typing
from atexit import register
from weakref import WeakMethod

from .ProxyServer import ProxyServer

LOGGER = logging.getLogger(__name__)


def main(port: int, rpc_port: typing.Optional[int] = None, backend: str = ""):
    """Run a PyVISA proxy server."""
    server = ProxyServer(port, rpc_port, backend)
    close_ref = WeakMethod(server.close)

    def call_close():
        meth = close_ref()
        if meth:
            meth()

    register(call_close)
    server.run()
    LOGGER.info("Server is shutting down.")


def parse_arguments(argv):
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--port",
        type=int,
        dest="port",
        default=5000,
        help="Port for zmq localhost binding",
    )
    parser.add_argument(
        "--rpc-port",
        type=int,
        dest="rpc_port",
        default=None,
        help="Custom RPC Port for zmq localhost binding",
    )
    parser.add_argument(
        "--backend",
        type=str,
        dest="backend",
        default="",
        help="Backend for pyvisa ResourceManager",
    )
    args = parser.parse_args(argv)
    return args


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s"
    )
    args = parse_arguments(sys.argv[1:])
    main(args.port, args.rpc_port, args.backend)
