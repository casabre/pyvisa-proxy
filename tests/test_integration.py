from pyvisa import ResourceManager

from pyvisa_proxy import ProxyServer
from pyvisa_proxy.ProxyResource import ProxyResource


def test_integration(sync_port, resource_name, executor, rm_sim):

    with ProxyServer(sync_port, "@sim") as server:
        executor.submit(server.run)
        rm = ResourceManager(f"localhost:{sync_port}@proxy")
        assert rm.list_resources() == rm_sim.list_resources()
        instr = rm.open_resource(resource_name)
        assert isinstance(instr, ProxyResource)
        resp = instr.query("*IDN?")
        assert resp == "SCPI,MOCK,VERSION_1.0"
        rm.close()
