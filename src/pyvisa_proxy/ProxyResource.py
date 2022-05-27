"""PyVISA-proxy resource which accesses VISA handles at server side.

:copyright: 2022 by PyVISA-proxy Authors, see AUTHORS for more details.
:license: MIT, see LICENSE for more details.
"""
import typing

from pyvisa import Resource

from .RpcClient import RpcClient


class ProxyResource(Resource):
    """PyVISA remote proxy resource which takes care of outgoing VISA calls."""

    def __init__(
        self,
        resource_cls,
        resource_name: str,
        host: str,
        rpc_port: int,
        **kwargs,
    ):
        """Initialize proxy resource."""
        self._rpc_client: typing.Optional[RpcClient] = RpcClient(
            host, rpc_port
        )
        self._resource_cls = resource_cls
        self._resource_name = resource_name
        # Open the resource
        self._rpc_client.request(
            None, "open_resource", args=(resource_name,), kwargs=kwargs
        )

    def __del__(self) -> None:
        """Clean up on garbage collection."""
        return self.close()

    def close(self) -> None:
        """Close remote session and zmq connection."""
        if self._rpc_client is not None:
            self._rpc_client.request(None, "close_resource")
            self._rpc_client.close()
            self._rpc_client = None
        return None

    def _is_fixed_attr(self, name: str) -> bool:
        return name in [
            "_rpc_client",
            "_resource_cls",
            "_resource_name",
            "_request",
            "_is_fixed_attr",
            "close",
        ]

    def __getattr__(self, name):
        """Overwritten base function in order to query calls via reflection.

        :param name: attribute name
        :type name: str
        :return: Any value
        :rtype: Any
        """
        if self._is_fixed_attr(name):
            return self[name]
        attr = getattr(self._resource_cls, name)
        if callable(attr):

            def wrapper(*args, **kwargs):
                return typing.cast(RpcClient, self._rpc_client).request(
                    name, "getattr", args=args, kwargs=kwargs
                )

            return wrapper
        return typing.cast(RpcClient, self._rpc_client).request(
            name, "getattr"
        )

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
        if self._is_fixed_attr(name):
            super().__setattr__(name, value)
            return
        attr = getattr(self._resource_cls, name)
        if callable(attr):
            raise AttributeError("Set should not be a callable")
        return typing.cast(RpcClient, self._rpc_client).request(
            name, "setattr", value=value
        )
