"""
PyVISA-remote client which accesses VISA handles at server side
"""
import platform
import pickle
import logging
import typing
from six import reraise
import zmq
import msgpack

LOGGER = logging.getLogger(__name__)


class CallableValue(object):
    def __init__(self, name: str, request: callable):
        self.name = name
        self._request = request

    def __call__(self, *args, **kwargs):
        return self._request(self.name, '__getattr__',
                             *args, value=None, **kwargs)


class RemoteClient:
    """
    PyVISA remote client which makes outgoing VISA calls

    :param object: object base class
    :type object: object
    """

    def __init__(self, resource: str, addr: str,
                 ctx: typing.Optional[zmq.Context] = None):
        self.resource = resource
        self.ctx = ctx or zmq.Context.instance()
        self.socket = self.ctx.socket(zmq.REQ)
        self.socket.identity = f'{platform.node()}-PyVisaRemoteClient'.encode()
        self.socket.connect(addr)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, trace):
        self.close()

    def __del__(self):
        self.close()

    def close(self):
        """Close zmq connection"""
        if self.socket.is_open():
            self.socket.close()
        self.ctx.term()

    @staticmethod
    def is_fixed_attr(name: str):
        return name in ['resource', 'ctx', 'socket', 'is_fixed_attr']

    def __getattr__(self, name):
        """
        Overwritten base function in order to query calls via reflection

        :param name: attribute name
        :type name: str
        :return: Any value
        :rtype: Any
        """
        if self.is_fixed_attr(name):
            return self[name]
        attr = super().__getattr__(name)
        if callable(attr):
            def wrapper(*args, **kwargs):
                return self._request(name, '__getattr__',
                                     *args, value=None, **kwargs)
            return wrapper
        return self._request(name, '__getattr__', None, None, None)

    def __setattr__(self, name, value):
        """
        Set a value at the remote VISA VisaRemoteClient

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
        attr = super().__getattr__(name)
        if callable(attr):
            raise AttributeError("Set should not be a callable")
        return self._request(name, '__setattr__', value, None, None)

    def _request(self, name: str, action: str, *args, value=None, **kwargs):
        """
        Send request via zmq to server

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
            'resources': self.resource,
            'name': name,
            'action': action,
            'value': value,
            'args': args,
            'kwargs': kwargs
        }
        self.socket.send_serialized(
            msg=message, serialize=msgpack.dumps)
        rep = self.socket.recv_serialized(deserialize=msgpack.loads)
        if 'exception' in rep:
            # Unfortunately, no simple and lightweight solution"
            # https://stackoverflow.com/a/45241491
            reraise(*pickle.loads(rep['exception']))
        return rep['value']
