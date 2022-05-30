import asyncio
import typing
import uuid

import dill as pickle
import pytest
import zmq
from six import reraise

from pyvisa_proxy import ProxyServer, __version__
from pyvisa_proxy.ProxyServer import SynchronizationProcessor


class Dummy(object):
    def query(*args, **kwargs):
        return ""


def create_message(
    name: typing.Optional[str],
    action: str,
    args=(),
    value=None,
    kwargs={},
):
    message = {
        "name": name,
        "action": action,
        "value": value,
        "args": args,
        "kwargs": kwargs,
    }
    return message


@pytest.fixture
def proxy_server(sync_port, run_infinite) -> ProxyServer:
    server = ProxyServer(sync_port, backend="@sim")
    run_infinite(server.run)
    yield server
    server.close()


@pytest.fixture
def proxy_resource(proxy_server, sync_port):
    ctx = zmq.Context.instance()
    socket = ctx.socket(zmq.REQ)
    sync_socket = ctx.socket(zmq.REQ)
    socket.identity = str(uuid.uuid4()).encode()
    sync_socket.identity = str(uuid.uuid4()).encode()
    try:
        sync_socket.connect(f"tcp://localhost:{sync_port}")
        sync_socket.send(b"")
        rep = pickle.loads(sync_socket.recv())
        rpc_port = rep["rpc_port"]
        socket.connect(f"tcp://localhost:{rpc_port}")
        yield socket
    finally:
        sync_socket.close()
        socket.close()


def open_resource(proxy_resource, resource_name):
    message = create_message(None, "open_resource", args=(resource_name,))
    return send_command(proxy_resource, message)


def send_command(proxy_resource, message: dict):
    proxy_resource.send(pickle.dumps(message))
    rep = pickle.loads(proxy_resource.recv())
    if "exception" in rep:
        reraise(*pickle.loads(rep["exception"]))
    return rep["value"]


def test_sync_up(rpc_port, sync_port, executor):
    backend = "@py"

    def run():
        sync_processor = SynchronizationProcessor(
            sync_port, rpc_port, backend, __version__
        )
        asyncio.run(sync_processor.call())

    executor.submit(run)
    ctx = zmq.Context.instance()
    sync_socket = ctx.socket(zmq.REQ)
    sync_socket.identity = str(uuid.uuid4()).encode()
    sync_socket.connect(f"tcp://localhost:{sync_port}")
    sync_socket.send(b"")
    rep = pickle.loads(sync_socket.recv())
    assert rep["rpc_port"] == rpc_port
    assert rep["backend"] == backend
    assert rep["version"] == __version__


def test_ports_identical():
    with pytest.raises(ValueError):
        ProxyServer(5000, 5000)


def test_open_resource(proxy_server, proxy_resource, resource_name):
    id = proxy_resource.identity.decode("utf-8")
    open_resource(proxy_resource, resource_name)
    assert id in proxy_server._rpc_processor.visa


def test_close_resource(proxy_server, proxy_resource, resource_name):
    id = proxy_resource.identity.decode("utf-8")
    open_resource(proxy_resource, resource_name)
    assert id in proxy_server._rpc_processor.visa
    message = create_message(None, "close_resource")
    send_command(proxy_resource, message)
    assert id not in proxy_server._rpc_processor.visa


def test_list_resources(proxy_server, proxy_resource, rm_sim):
    proxy_resource.identity.decode("utf-8")
    message = create_message(None, "list_resources")
    rep = send_command(proxy_resource, message)
    assert isinstance(rep, tuple)
    ref = rm_sim.list_resources()
    assert rep == ref


def test_getattr(proxy_server, proxy_resource, resource_name):
    id = proxy_resource.identity.decode("utf-8")
    open_resource(proxy_resource, resource_name)
    assert id in proxy_server._rpc_processor.visa
    message = create_message("timeout", "getattr")
    rep = send_command(proxy_resource, message)
    assert rep == proxy_server._rpc_processor.visa[id][0].timeout


def test_setattr(proxy_server, proxy_resource, resource_name):
    id = proxy_resource.identity.decode("utf-8")
    open_resource(proxy_resource, resource_name)
    assert id in proxy_server._rpc_processor.visa
    message = create_message("timeout", "setattr", value=1)
    rep = send_command(proxy_resource, message)
    assert rep is None
    assert proxy_server._rpc_processor.visa[id][0].timeout == 1
