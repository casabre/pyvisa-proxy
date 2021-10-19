import pytest
from pyvisa_remote import RemoteClient
import zmq
from .utils import recv_compare_and_reply
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=1)
port = 5000

resource_str = 'USB0::0x0aad::0021::123456'


@pytest.fixture
def client():
    client = RemoteClient(resource_str, f'tcp://localhost:{port}')
    yield client
    client.close()


@pytest.fixture
def emulated_server():
    ctx = zmq.Context.instance()
    socket = ctx.socket(zmq.REP)
    socket.bind(f'tcp://*:{port}')
    yield socket
    socket.close()
    ctx.term()


@pytest.fixture
def compare_and_reply(emulated_server):
    def func(expected, reply):
        return executor.submit(recv_compare_and_reply,
                               emulated_server, expected,
                               reply)
    return func


def create_getattr_msg(name: str, *args, **kwargs):
    message = {
        'resources': resource_str,
        'name': name,
        'action': '__getattr__',
        'args': args,
        'kwargs': kwargs,
    }
    return message


def test_client_success(client, compare_and_reply):
    idn = 'USB device'
    future = compare_and_reply(create_getattr_msg(
        'query', '*IDN?'), {'value': idn})
    client.query('*IDN?') == idn
    assert future.result()
