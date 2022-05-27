"""RPC-client which accesses corresponding attributes at server side.

:copyright: 2022 by PyVISA-proxy Authors, see AUTHORS for more details.
:license: MIT, see LICENSE for more details.
"""
import logging
import platform
import typing
import uuid

import dill as pickle
import zmq
from six import reraise

from .version import get_version

VERSION = get_version()
LOGGER = logging.getLogger(__name__)


class RpcClient(object):
    """PyVISA remote proxy resource which takes care of outgoing VISA calls."""

    def __init__(self, host: str, rpc_port: int):
        """Initialize RPC client."""
        self._rpc_port = rpc_port
        self._identity = f"{platform.node()}.{uuid.uuid4()}"
        self._ctx = zmq.Context.instance()
        self._socket = self._ctx.socket(zmq.REQ)  # pylint: disable=E1101
        self._socket.identity = self._identity.encode()
        self._socket.connect(f"tcp://{host}:{self._rpc_port}")

    def __del__(self) -> None:
        """Clean up on garbage collection."""
        return self.close()

    def close(self) -> None:
        """Close zmq connection."""
        self._socket.close()
        return None

    def request(
        self,
        name: typing.Optional[str],
        action: str,
        args: tuple = (),
        value=None,
        kwargs: dict = {},
    ) -> typing.Any:
        """Send request via zmq to server.

        :param name: attribute name
        :type name: typing.Optional[str]
        :param action: getattr or setattr or open_resource or list_resources
        :type action: str
        :param value: Value for __setattr__, defaults to None
        :type value: Any, optional
        :raises Exception: reraise Exception from server at client side
        :return: Any provided value
        :rtype: Any
        """
        message = {
            "name": name,
            "action": action,
            "value": value,
            "args": args,
            "kwargs": kwargs,
        }
        self._socket.send(pickle.dumps(message))
        rep = pickle.loads(self._socket.recv())
        if "exception" in rep:
            # Unfortunately, no simple and lightweight solution"
            # https://stackoverflow.com/a/45241491
            reraise(*pickle.loads(rep["exception"]))
        return rep["value"]
