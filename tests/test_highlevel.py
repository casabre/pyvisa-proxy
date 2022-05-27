import dill as pickle
import pytest
import zmq
from pyvisa import ResourceManager

from pyvisa_proxy import __version__
from pyvisa_proxy.highlevel import (
    CompatibilityError,
    ProxyVisaLibrary,
    check_for_version_compatibility,
    sync_up,
)


def test_sync_up(rpc_port, sync_port, executor):
    ref_backend = "@py"
    ctx = zmq.Context.instance()
    sync_socket = ctx.socket(zmq.REP)
    try:
        sync_socket.bind(f"tcp://*:{sync_port}")
        future = executor.submit(sync_up, "localhost", sync_port, 5)
        sync_socket.recv_multipart()
        sync_socket.send(
            pickle.dumps(
                {
                    "rpc_port": rpc_port,
                    "backend": ref_backend,
                    "version": __version__,
                }
            ),
        )
        rpc_port, backend, version = future.result()
        assert rpc_port == rpc_port
        assert ref_backend == backend
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


def test_timeout(sync_port):
    with pytest.raises(TimeoutError):
        sync_up("localhost", sync_port, 1)


def test_new_ProxyVisaLibrary_without_URL():
    with pytest.raises(OSError):
        ResourceManager("@proxy")
    pass


def test_new_ProxyVisaLibrary(emulated_server_with_sync, sync_port):
    rm = ResourceManager(f"localhost:{sync_port}@proxy")
    assert isinstance(rm.visalib, ProxyVisaLibrary)
