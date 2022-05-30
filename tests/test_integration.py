import time
from multiprocessing import Process

import pytest
import pyvisa
from packaging.version import parse
from pyvisa import ResourceManager

from pyvisa_proxy import ProxyServer, main
from pyvisa_proxy.ProxyResource import ProxyResource


@pytest.mark.parametrize("static_rpc_port", [True, False])
def test_integration_with_class(
    static_rpc_port,
    sync_port,
    rpc_port,
    resource_name,
    executor,
    rm_sim,
    idn_string,
    query_string,
):
    if parse(pyvisa.__version__) < parse("1.12.0"):
        pytest.skip("PyVISA-proxy implementation in PyVISA is missing.")

    test_rpc_port = rpc_port if static_rpc_port else None
    with ProxyServer(sync_port, test_rpc_port, "@sim") as server:
        executor.submit(server.run)
        get_resource_and_test(
            sync_port, resource_name, rm_sim, idn_string, query_string
        )
        server.close()


@pytest.mark.parametrize("static_rpc_port", [True, False])
def test_integration_with_main(
    static_rpc_port,
    sync_port,
    rpc_port,
    resource_name,
    rm_sim,
    idn_string,
    query_string,
):
    if parse(pyvisa.__version__) < parse("1.12.0"):
        pytest.skip("PyVISA-proxy implementation in PyVISA is missing.")
    test_rpc_port = rpc_port if static_rpc_port else None
    executor = Process(target=main, args=(sync_port, test_rpc_port, "@sim"))
    try:
        executor.start()
        get_resource_and_test(
            sync_port, resource_name, rm_sim, idn_string, query_string
        )
    finally:
        executor.terminate()
        count = 0
        while executor.is_alive():
            time.sleep(0.001)
            count += 1
            if count == 100:
                TimeoutError("Subprocess did not terminate in time.")


def get_resource_and_test(
    sync_port, resource_name: str, rm_sim, idn: str, query_string: str
):
    rm = ResourceManager(f"localhost:{sync_port}@proxy")
    resources = rm.list_resources()
    assert resources == rm_sim.list_resources()
    instr = rm.open_resource(resource_name)
    assert isinstance(instr, ProxyResource)
    resp = instr.query(query_string)
    assert resp == idn
    rm.close()
