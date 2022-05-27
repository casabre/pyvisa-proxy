"""Run PyVISA-proxy server as service.

:copyright: 2022 by PyVISA-proxy Authors, see AUTHORS for more details.
:license: MIT, see LICENSE for more details.
"""
import argparse
import logging
from atexit import register
from weakref import WeakMethod

from .ProxyServer import ProxyServer

LOGGER = logging.getLogger(__name__)


def main(port: int, backend: str = ""):
    """Run a PyVISA proxy server."""
    server = ProxyServer(port, backend)
    close_ref = WeakMethod(server.close)

    def call_close():
        meth = close_ref()
        if meth:
            meth()

    register(call_close)
    server.run()
    LOGGER.info("Server is shutting down.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s"
    )
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--port",
        type=int,
        dest="port",
        default=5000,
        help="Port for zmq localhost binding",
    )
    parser.add_argument(
        "--backend",
        type=str,
        dest="backend",
        default="",
        help="Backend for pyvisa ResourceManager",
    )
    args = parser.parse_args()
    main(args.port, args.backend)
