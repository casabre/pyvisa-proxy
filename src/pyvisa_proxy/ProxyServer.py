"""
PyVISA-proxy server which provides access to VISA handles
"""
import asyncio
import json
import logging
import os
import sys
import time
import typing
from multiprocessing import Process

import cbor2 as cbor
import dill as pickle
import pyvisa
import zmq
import zmq.asyncio
from jsonschema import validate
from tblib import pickling_support

from .version import get_version

pickling_support.install()

VERSION = get_version()
LOGGER = logging.getLogger(__name__)

with open(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "data", "job.schema.json")
    ),
    "r",
    encoding="utf-8",
) as fp:
    schema = json.load(fp)


def sync_up(sync_port: int, rpc_port: int, version):
    async def run():
        ctx = zmq.asyncio.Context.instance()
        socket = ctx.socket(zmq.REP)
        socket.bind(f"tcp://*:{sync_port}")
        while True:
            address, _, _ = await socket.recv_multipart()
            reply = {"rpc_port": rpc_port, "version": version}
            await socket.send_multipart([address, b"", cbor.dumps(reply)])

    asyncio.run(run())


class ProxyServer:
    """PyVISA remote proxy server which handles incoming VISA calls.

    :param object: object base class
    :type object: object
    """

    def __init__(self, port):
        self.ctx = zmq.asyncio.Context.instance()
        self._socket = self.ctx.socket(zmq.REP)
        rpc_port = self._socket.bind_to_random_port(f"tcp://*")
        self._sync_process = Process(target=sync_up, args=(rpc_port, VERSION))
        self._sync_process.start()
        self._visa_handle = {}
        self._lock = asyncio.Lock()
        try:
            self._rm = pyvisa.ResourceManager()
        except Exception:
            self._rm = pyvisa.ResourceManager("@py")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, trace):
        self.close()

    def __del__(self):
        self.close()

    def close(self):
        """Close, sync-process, zmq connection and VISA handles"""
        if self._socket is not None:
            self._socket.close()
            self._socket = None
        if self._sync_process is not None:
            self._sync_process.terminate()
            self._sync_process = None
        for handle in self._visa_handle.values():
            handle.close()

    def run(self):
        """Run server with asyncio runner"""
        asyncio.run(self._run())

    async def _run(self):
        """
        Async runner
        """
        while True:
            msg = await self._socket.recv_multipart()
            reply = await self._call_pyvisa(msg)
            await self._socket.send_multipart(reply)

    async def _call_pyvisa(self, msg):
        """Call pyvisa with job information from client.

        :param msg: job description message
        :type msg: zmq.Frage
        :return: Result data
        :rtype: zmq.Frame
        """
        address, _, request = msg
        job_data = cbor.loads(request)
        LOGGER.debug(f"Job {job_data} from {address}")
        result = {}
        try:
            validate(job_data, schema)
            res = await self._execute_job(job_data)
        except Exception as err:
            # Unfortunately, no simple and lightweight solution
            # https://stackoverflow.com/a/45241491
            LOGGER.error(f"Job {job_data} from {address} threw {err}")
            result["exception"] = pickle.dumps(sys.exc_info())
        else:
            LOGGER.debug(f"Job {job_data} from {address} result: {res}")
            result["value"] = res
        return [address, b"", cbor.dumps(result)]

    async def _execute_job(
        self, job_data: dict
    ) -> typing.Optional[typing.Any]:
        """Execute pyvisa job data.

        :return: Result data dictionary
        :rtype: dict or any base type
        """
        loop = asyncio.get_running_loop()
        visa = await self._get_visa_handle(job_data["resource"])
        if job_data["action"] == "getattr":
            attribute = await loop.run_in_executor(
                None, getattr, visa, job_data["name"]
            )
            if callable(attribute):
                args = tuple(
                    [x for x in job_data.get("args", ()) if x is not None]
                )
                kwargs = job_data.get("kwargs", {})
                res = await loop.run_in_executor(
                    None, lambda: attribute(*args, **kwargs)
                )
            else:
                res = attribute
        else:
            await loop.run_in_executor(
                None, setattr, visa, job_data["name"], job_data["value"]
            )
            res = None
        return res

    async def _get_visa_handle(self, resource: str) -> pyvisa.Resource:
        """Get VISA handle in an asyncio manner.

        :param resource: VISA information resource string
        :type resource: str
        :return: pyvisa resource handle
        :rtype: pyvisa.Resource
        """
        loop = asyncio.get_running_loop()
        if resource in self._visa_handle:
            self._visa_handle[resource][1] = time.time()
            return self._visa_handle[resource][0]
        async with self._lock:
            self._visa_handle[resource] = [
                await loop.run_in_executor(
                    None, self._rm.open_resource, resource
                ),
                time.time(),
            ]
        return self._visa_handle[resource][0]
