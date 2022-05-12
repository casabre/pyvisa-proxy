.. _server:

Setting up the PyVISA-proxy server
==================================

PyVISA-proxy needs a remote server in order to provide access to plugged in
instruments.

You can run the PyVISA-proxy server calling the package with the 
synchronization port:

.. code-block: shell
    
    pyvisa_proxy --port 5000

An asynchronous server process will start which can be addressed from the
remote client interface.
