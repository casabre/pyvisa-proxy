import typing
import uuid
from multiprocessing import Process

import dill as pickle
import pytest
import zmq
from six import reraise

from pyvisa_proxy import ProxyServer, __version__
from pyvisa_proxy.ProxyServer import sync_up


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
def proxy_server(sync_port, executor, rm_sim) -> ProxyServer:
    server = ProxyServer(sync_port)
    server._rm = rm_sim
    executor.submit(server.run)
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
    proxy_resource.send(pickle.dumps(message))
    return pickle.loads(proxy_resource.recv())


def send_command(proxy_resource, message: bytes):
    proxy_resource.send(pickle.dumps(message))
    rep = pickle.loads(proxy_resource.recv())
    if "exception" in rep:
        reraise(*pickle.loads(rep["exception"]))
    return rep["value"]


def test_sync_up(rpc_port, sync_port):
    backend = "@py"
    p = Process(
        target=sync_up,
        args=(sync_port, rpc_port, backend, __version__),
    )
    ctx = zmq.Context.instance()
    sync_socket = ctx.socket(zmq.REQ)
    sync_socket.identity = str(uuid.uuid4()).encode()
    try:
        p.start()
        sync_socket.connect(f"tcp://localhost:{sync_port}")
        sync_socket.send(b"")
        rep = pickle.loads(sync_socket.recv())
        assert rep["rpc_port"] == rpc_port
        assert rep["backend"] == backend
        assert rep["version"] == __version__
    finally:
        p.terminate()
        sync_socket.close()


def test_open_resource(proxy_server, proxy_resource, resource_name):
    id = proxy_resource.identity.decode("utf-8")
    open_resource(proxy_resource, resource_name)
    assert id in proxy_server._visa


def test_close_resource(proxy_server, proxy_resource, resource_name):
    id = proxy_resource.identity.decode("utf-8")
    open_resource(proxy_resource, resource_name)
    assert id in proxy_server._visa
    message = create_message(None, "close_resource")
    send_command(proxy_resource, message)
    assert id not in proxy_server._visa


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
    assert id in proxy_server._visa
    message = create_message("timeout", "getattr")
    rep = send_command(proxy_resource, message)
    assert rep == 2000


def test_setattr(proxy_server, proxy_resource, resource_name):
    id = proxy_resource.identity.decode("utf-8")
    open_resource(proxy_resource, resource_name)
    assert id in proxy_server._visa
    message = create_message("timeout", "setattr", value=1)
    rep = send_command(proxy_resource, message)
    assert rep is None
    assert proxy_server._visa[id][0].timeout == 1
