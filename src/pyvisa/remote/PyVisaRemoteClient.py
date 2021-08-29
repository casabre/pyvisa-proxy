import zmq
import msgpack
import platform
import pickle
from six import reraise
import logging

LOGGER = logging.getLogger(__name__)


class PyVisaRemoteClient(object):
    def __init__(self, resource: str, host: str, port: int):
        super(PyVisaRemoteClient, self).__init__()
        self._ctx = zmq.Context()
        self._socket = zmq.Socket(zmq.REQ)
        self._socket.identity = f'{platform.node()}-VisaRemoteClient'
        self._socket.connect(f'tcpip://{host}:{port}')
        self._resource_str = resource

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, trace):
        self.close()

    def __del__(self):
        self.close()

    def close(self):
        if self._socket.is_open():
            self._socket.close()
        self._ctx.term()

    def __getattr__(self, name):
        attr = getattr(self, name)
        if callable(attr):
            def wrapper(*args, **kwargs):
                return self._request(name, '__getattr__',
                                     None, *args, **kwargs)
            return wrapper
        else:
            return self._request(name, '__getattr__', None, None, None)

    def __setattr__(self, name, value):
        attr = getattr(self, name)
        if callable(attr):
            raise AttributeError("Set should not be a callable")
        else:
            return self._request(name, '__setattr__', value, None, None)

    def _request(self, name: str, action: str, value=None, *args, **kwargs):
        message = {
            'resources': self._resource_str,
            'name': name,
            'action': action,
            'value': value,
            'args': args,
            'kwargs': kwargs
        }
        self._socket.send_serialized(
            msg=message, serialize=msgpack.dumps)
        rep = self._socket.recv_serialized(deserialize=msgpack.loads)
        if 'exception' in rep:
            # Unfortunately, no simple and lightweight solution"
            # https://stackoverflow.com/a/45241491
            reraise(*pickle.loads(rep['exception']))
        return rep['value']
