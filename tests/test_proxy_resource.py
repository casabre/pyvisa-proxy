import typing

import dill as pickle
import pytest

from pyvisa_proxy.ProxyResource import ProxyResource

from .utils import Dummy

RESOURCE_NAME = "USB0::0x0aad::0021::123456"


@pytest.fixture
def client(emulated_server, rpc_port, executor):
    def get_client():
        c = ProxyResource(Dummy, RESOURCE_NAME, "localhost", rpc_port)
        return c

    future = executor.submit(get_client)
    emulated_server.recv()
    emulated_server.send(pickle.dumps({"value": 0}))
    client = future.result()
    yield client
    if client._rpc_client is not None:
        future = executor.submit(client.__del__)
        emulated_server.recv()
        emulated_server.send(pickle.dumps({"value": 0}))
        future.result()


def create_getattr_msg(
    name: str, *args, value: typing.Optional[typing.Any] = None, **kwargs
):
    message = {
        "name": name,
        "action": "getattr",
        "args": args,
        "kwargs": kwargs,
        "value": value,
    }
    return message


def test_client_success(client, compare_and_reply):
    idn = "USB device"
    future = compare_and_reply(
        create_getattr_msg("query", "*IDN?"), {"value": idn}
    )
    ret = client.query("*IDN?")
    assert future.result()
    assert ret == idn


def test_close(client, emulated_server, executor):
    def server_close():
        emulated_server.recv()
        emulated_server.send(pickle.dumps({"value": 0}))
        return None

    future = executor.submit(server_close)
    client.close()
    future.result()
    assert client._rpc_client is None
