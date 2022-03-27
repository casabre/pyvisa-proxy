from concurrent.futures import ThreadPoolExecutor

import pytest
import zmq
import cbor2 as cbor
import typing

from pyvisa_proxy import ProxyResource, __version__
from pyvisa_proxy.ProxyResource import (
    sync_up,
    check_for_version_compatibility,
    CompatibilityError,
)

from .utils import recv_compare_and_reply

EXECUTOR = ThreadPoolExecutor(max_workers=1)
PORT = 5000
RESOURCE_NAME = "USB0::0x0aad::0021::123456"


class Dummy(object):
    def query(*args, **kwargs):
        return ""


@pytest.fixture
def client():
    ctx = zmq.Context.instance()
    sync_socket = ctx.socket(zmq.REP)
    try:
        sync_socket.bind(f"tcp://*:{PORT}")
        future = EXECUTOR.submit(
            lambda: ProxyResource(Dummy, RESOURCE_NAME, "localhost", PORT)
        )
        sync_socket.recv()
        sync_socket.send(
            cbor.dumps({"rpc_port": PORT, "version": __version__})
        )
    finally:
        sync_socket.close()
    client = future.result()
    yield client
    client.close()


@pytest.fixture
def emulated_server():
    ctx = zmq.Context.instance()
    socket = ctx.socket(zmq.REP)
    socket.bind(f"tcp://*:{PORT}")
    yield socket
    socket.close()


@pytest.fixture
def compare_and_reply(emulated_server):
    def func(expected, reply):
        return EXECUTOR.submit(
            recv_compare_and_reply, emulated_server, expected, reply
        )

    return func


def create_getattr_msg(
    name: str, *args, value: typing.Optional[typing.Any] = None, **kwargs
):
    message = {
        "resources": RESOURCE_NAME,
        "name": name,
        "action": "getattr",
        "args": args,
        "kwargs": kwargs,
        "value": value,
    }
    return message


def test_sync_up():
    ctx = zmq.Context.instance()
    sync_socket = ctx.socket(zmq.REP)
    try:
        sync_socket.bind(f"tcp://*:{PORT}")
        future = EXECUTOR.submit(sync_up, "localhost", PORT, 5)
        sync_socket.recv_multipart()
        sync_socket.send(
            cbor.dumps({"rpc_port": PORT, "version": __version__}),
        )
        rpc_port, version = future.result()
        assert rpc_port == PORT
        assert version == __version__
    finally:
        sync_socket.close()


@pytest.mark.parametrize(
    ("version", "verdict"), [("0.0.1", True), ("0.2.0", False)]
)
def test_check_version_compatibility(version, verdict):
    if verdict:
        check_for_version_compatibility(version)
    else:
        with pytest.raises(CompatibilityError):
            check_for_version_compatibility(version)


def test_timeout():
    with pytest.raises(TimeoutError):
        ProxyResource(Dummy, RESOURCE_NAME, "localhost", PORT, 1)


def test_client_success(client, compare_and_reply):
    idn = "USB device"
    future = compare_and_reply(
        create_getattr_msg("query", "*IDN?"), {"value": idn}
    )
    client.query("*IDN?") == idn
    assert future.result()
