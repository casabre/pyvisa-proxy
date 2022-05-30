import typing

import pytest

from pyvisa_proxy.__main__ import parse_arguments


@pytest.mark.parametrize(
    "port, rpc_port, backend",
    [
        (5000, None, None),
        (
            5000,
            5001,
            None,
        ),
        (5000, 5001, "@py"),
        (5000, None, "@py"),
        (None, 5001, None),
        (None, None, "@py"),
    ],
)
def test_parsing(
    port: typing.Optional[int],
    rpc_port: typing.Optional[int],
    backend: typing.Optional[str],
):
    argv = []
    if port is not None:
        argv.extend(["--port", str(port)])
        port_val = port
    else:
        port_val = 5000
    if rpc_port is not None:
        argv.extend(["--rpc-port", str(rpc_port)])
        rpc_port_val = rpc_port
    else:
        rpc_port_val = None
    if backend is not None:
        argv.extend(["--backend", str(backend)])
        backend_val = backend
    else:
        backend_val = ""
    args = parse_arguments(argv)
    assert args.port == port_val
    assert args.rpc_port == rpc_port_val
    assert args.backend == backend_val
