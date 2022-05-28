:orphan:


PyVISA-proxy: Remote backend for PyVISA
========================================

.. image:: _static/logo-full.jpg
   :alt: PyVISA


PyVISA-proxy is a backend for PyVISA_. It allows you to connect to remote
devices as they where locally plugged in. It addresses mainly legacy protocols
like GPIB or not ethernet based connections as USB. But you can use it also to
tunnel specific connections which could be blocked by a firewall, like VXI11.

You can select the PyVISA-proxy backend using **@proxy** with the PyVISA proxy
server IP address when instantiating the visa Resource Manager:

    >>> import visa
    >>> rm = visa.ResourceManager('YourProxyServerIp:YourProxyServerPort@proxy')
    >>> rm.list_resources()
    ('ASRL1::INSTR')
    >>> inst = rm.open_resource('ASRL1::INSTR', read_termination='\n')
    >>> print(inst.query("?IDN"))


That's all! Except for **YourProxyServerIp:YourProxyServerPort@proxy**, the
code is exactly what you would write in order to use the VISA backend for
PyVISA.

Installation
============

Using pip::

    pip install -U pyvisa-proxy

You can report a problem or ask for features in the `issue tracker`_.

.. _PyVISA: http://pyvisa.readthedocs.org/
.. _PyVISA-proxy: http://pyvisa-proxy.readthedocs.org/
.. _PyPI: https://pypi.python.org/pypi/PyVISA-proxy
.. _GitHub: https://github.com/casabre/pyvisa-proxy
.. _`issue tracker`: https://github.com/casabre/pyvisa-proxy/issues


User Guide
----------

.. toctree::
    :maxdepth: 1

    server
