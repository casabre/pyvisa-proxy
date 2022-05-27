from multiprocessing import Process

import pytest
import pyvisa
from packaging.version import parse
from pyvisa import ResourceManager

from pyvisa_proxy import ProxyServer, main
from pyvisa_proxy.ProxyResource import ProxyResource


def test_integration_with_class(
    sync_port, resource_name, executor, rm_sim, idn_string, query_string
):
    if parse(pyvisa.__version__) < parse("1.12.0"):
        pytest.skip("PyVISA-proxy implementation in PyVISA is missing.")

    with ProxyServer(sync_port, "@sim") as server:
        executor.submit(server.run)
        get_resource_and_test(
            sync_port, resource_name, rm_sim, idn_string, query_string
        )


def test_integration_with_main(
    sync_port, resource_name, rm_sim, idn_string, query_string
):
    if parse(pyvisa.__version__) < parse("1.12.0"):
        pytest.skip("PyVISA-proxy implementation in PyVISA is missing.")
    executor = Process(target=main, args=(sync_port, "@sim"))
    try:
        executor.start()
        get_resource_and_test(
            sync_port, resource_name, rm_sim, idn_string, query_string
        )
    finally:
        executor.terminate()


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
