"""
PyVISA-proxy client which accesses VISA handles at server side
"""
import logging
import pickle
import platform
from packaging.version import parse

import cbor2 as cbor
import zmq
from six import reraise

from .version import get_version

VERSION = get_version()
LOGGER = logging.getLogger(__name__)


class CompatibilityError(Exception):
    pass


def sync_up(host: str, sync_port: int, timeout: int):
    ctx = zmq.Context.instance()
    socket = ctx.socket(zmq.REQ)
    socket.identity = f"{platform.node()}-PyVisaProxyClient".encode()
    socket.connect(f"tcp://{host}:{sync_port}")
    try:
        socket.send(b"")
        polled = socket.poll(timeout=timeout * 1000)
        if polled == 0:
            raise TimeoutError(
                "Establishing a connection to PyVISA proxy timed out."
            )
        reply = cbor.loads(socket.recv())
        return reply.get("rpc_port"), reply.get("version")
    finally:
        socket.close()


def check_for_version_compatibility(version):
    resource_version = parse(VERSION)
    server_version = parse(version)
    if resource_version.release < server_version.release:
        raise CompatibilityError(
            f"Proxy server version {version} is to great."
        )


class ProxyResource:
    """PyVISA remote proxy resource which takes care of outgoing VISA calls."""

    def __init__(
        self,
        resource_cls,
        resource_name: str,
        host: str,
        port: int,
        timeout: int = 2,
    ):
        self.resource_cls = resource_cls
        self.resource_name = resource_name
        rpc_port, version = sync_up(host, port, timeout)
        check_for_version_compatibility(version)
        self.ctx = zmq.Context.instance()
        self.socket = self.ctx.socket(zmq.REQ)
        self.socket.identity = f"{platform.node()}-PyVisaProxyClient".encode()
        self.socket.connect(f"tcp://{host}:{rpc_port}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, trace):
        self.close()

    def __del__(self):
        self.close()

    def close(self):
        """Close zmq connection"""
        self.socket.close()

    @staticmethod
    def is_fixed_attr(name: str):
        return name in [
            "resource_cls",
            "resource_name",
            "ctx",
            "socket",
            "is_fixed_attr",
            "close",
        ]

    def __getattr__(self, name):
        """Overwritten base function in order to query calls via reflection.

        :param name: attribute name
        :type name: str
        :return: Any value
        :rtype: Any
        """
        if self.is_fixed_attr(name):
            return self[name]
        attr = getattr(self.resource_cls, name)
        if callable(attr):

            def wrapper(*args, **kwargs):
                return self._request(
                    name, "getattr", *args, value=None, **kwargs
                )

            return wrapper
        return self._request(name, "getattr", None, None, None)

    def __setattr__(self, name, value):
        """Set a value at the remote VISA VisaRemoteClient.

        :param name: attribute __name__
        :type name: str
        :param value: value to set
        :type value: Any
        :raises AttributeError: if a callable was provided
        :return: Usually None
        :rtype: Any
        """
        if self.is_fixed_attr(name):
            super().__setattr__(name, value)
            return
        attr = getattr(self.resource_cls, name)
        if callable(attr):
            raise AttributeError("Set should not be a callable")
        return self._request(name, "setattr", value, None, None)

    def _request(self, name: str, action: str, *args, value=None, **kwargs):
        """Send request via zmq to server.

        :param name: attribute name
        :type name: str
        :param action: __getattr__ or __setattr__
        :type action: str
        :param value: Value for __setattr__, defaults to None
        :type value: Any, optional
        :raises Exception: reraise Exception from server at client side
        :return: Any provided value
        :rtype: Any
        """
        message = {
            "resources": self.resource_name,
            "name": name,
            "action": action,
            "value": value,
            "args": args,
            "kwargs": kwargs,
        }
        self.socket.send(cbor.dumps(message))
        rep = cbor.loads(self.socket.recv())
        if "exception" in rep:
            # Unfortunately, no simple and lightweight solution"
            # https://stackoverflow.com/a/45241491
            reraise(*pickle.loads(rep["exception"]))
        return rep["value"]
