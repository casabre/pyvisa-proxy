# PyVISA-proxy

This plugin should extend PyVISA's funtionality mainly in order to address local hardware which is attached to a remote node, e.g. USB or GPIB. In the end, you can decouple your VISA instrument hosting where you need bare metal nodes and the test script runner.

## Getting started

### Installation

Using pip:

```shell
pip install pyvisa-proxy
```

### Server

In order to make devices remotely available, just run the PyVISA-remote server on your node. The server will open new VISA resources per request. Just run

```shell
python -m pyivsa_proxy --port 5000
```

in order to host your "local" connections. Use any available port for network sharing.

### Client

Use a client like a normal PyVISA class. The calls will be forwarded by reflection to the server. In order to get started, use the following snippet in your code.

```python
from pyvisa_proxy import RemoteClient

instr = RemoteClient(resource='GPIB0::1::INSTR', host='my-gpib-host.net', port=5000)
print(instr.query('*IDN?'))
```

## Roadmap

This should shortly outline the project goals within a version time line.

| Version | Description                                                                                                                |
| ------- | -------------------------------------------------------------------------------------------------------------------------- |
| 0.1.0   | Running standalone in RemoteServer and RemoteClient configuration                                                          |
| 0.2.0   | Integrate into pyvisa a compatible plugin in order to extend ResourceManager. Should reflect typing better on client side. |

## Contributing

I welcome any contributions, enhancements, and bug-fixes.  [Open an issue](https://github.com/casabre/pyvisa-remote/issues) on GitHub and [submit a pull request](https://github.com/casabre/pyvisa-remote/pulls).

## License

pyvisa-remote is 100% free and open-source, under the [MIT license](LICENSE). Use it however you want.

This package is [Treeware](https://treeware.earth). If you use it in production, then we ask that you [**buy the world a tree**](https://plant.treeware.earth/casabre/pyvisa-remote) to thank us for our work. By contributing to the Treeware forest you’ll be creating employment for local families and restoring wildlife habitats.
