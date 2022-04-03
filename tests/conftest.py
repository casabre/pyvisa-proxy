from concurrent.futures import ThreadPoolExecutor

import pytest
import pyvisa
import zmq

from pyvisa_proxy import __version__

from .utils import recv_compare_and_reply, sync_up_reply


@pytest.fixture
def resource_name() -> str:
    return "USB::0x1111::0x2222::0x4444::INSTR"


@pytest.fixture
def rpc_port() -> int:
    return 5000


@pytest.fixture
def sync_port(rpc_port) -> int:
    return rpc_port + 1


@pytest.fixture(scope="session")
def executor() -> ThreadPoolExecutor:
    executor = ThreadPoolExecutor()
    yield executor
    executor.shutdown(wait=False, cancel_futures=True)


@pytest.fixture
def backend() -> str:
    return "@py"


@pytest.fixture
def emulated_server(rpc_port):
    ctx = zmq.Context.instance()
    socket = ctx.socket(zmq.REP)
    try:
        socket.bind(f"tcp://*:{rpc_port}")
        yield socket
    finally:
        socket.close()


@pytest.fixture
def emulated_server_with_sync(
    emulated_server, rpc_port, sync_port, executor, backend
):
    future = executor.submit(
        sync_up_reply, sync_port, rpc_port, backend, __version__
    )
    yield emulated_server
    future.result()


@pytest.fixture
def rm_sim() -> pyvisa.ResourceManager:
    return pyvisa.ResourceManager("@sim")


@pytest.fixture
def compare_and_reply(emulated_server, executor):
    def func(expected, reply):
        return executor.submit(
            recv_compare_and_reply, emulated_server, expected, reply
        )

    return func
