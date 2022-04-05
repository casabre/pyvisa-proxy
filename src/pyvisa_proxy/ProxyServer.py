"""
    pyvisa-proxy.ProxyServer
    ~~~~~~~~~~~~~~~~~~~~

    PyVISA-proxy server which provides access to VISA handles.

    :copyright: 2022 by PyVISA-proxy Authors, see AUTHORS for more details.
    :license: MIT, see LICENSE for more details.
"""
import asyncio
import json
import logging
import os
import sys
import time
import typing
from atexit import register
from multiprocessing import Process
from threading import Event

import dill as pickle
import pyvisa
import zmq
import zmq.asyncio
from jsonschema.validators import extend, validator_for
from pyvisa import InvalidSession
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
    REFERENCE = validator_for(schema)
    VALIDATOR = extend(
        REFERENCE,
        type_checker=REFERENCE.TYPE_CHECKER.redefine(
            "array",
            lambda checker, instance: REFERENCE.TYPE_CHECKER.is_type(
                instance, "array"
            )
            or isinstance(instance, tuple),
        ),
    )(schema=schema)


def sync_up(sync_port: int, rpc_port: int, backend: str, version: str):
    """
    Provide an endpoint for Server - Client synchronization.

    :param sync_port: Socket port for synchronization.
    :type sync_port: int
    :param rpc_port: Socket port for RPC calls.
    :type rpc_port: int
    :param backend: Set PyVISA backend.
    :type backend: str
    :param version: Package version.
    :type version: str
    """
    ctx = zmq.asyncio.Context.instance()
    socket = ctx.socket(zmq.ROUTER)  # pylint: disable=E1101
    socket.bind(f"tcp://*:{sync_port}")
    register(lambda: socket.close())

    async def run():
        nonlocal socket
        while True:
            address, _, _ = await socket.recv_multipart()
            reply = {
                "rpc_port": rpc_port,
                "backend": backend,
                "version": version,
            }
            await socket.send_multipart([address, b"", pickle.dumps(reply)])

    asyncio.run(run())


class ProxyServer:
    """
    PyVISA remote proxy server which handles incoming VISA calls.

    :param object: object base class
    :type object: object
    """

    def __init__(self, port: int, backend: str = ""):
        self._rm = pyvisa.ResourceManager(backend)
        self.ctx = zmq.asyncio.Context.instance()
        self._socket = self.ctx.socket(zmq.ROUTER)  # pylint: disable=E1101
        rpc_port = self._socket.bind_to_random_port("tcp://*")
        self._sync_process: typing.Optional[Process] = Process(
            target=sync_up,
            args=(
                port,
                rpc_port,
                backend,
                VERSION,
            ),
        )
        self._sync_process.start()
        self._visa: typing.Dict[str, list] = {}
        self._stop = Event()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, trace):
        self.close()

    def __del__(self):
        self.close()

    def close(self):
        """Close sync-process, zmq connection and VISA handles"""
        self._stop.set()
        if self._socket is not None:
            self._socket.close()
            self._socket = None
        if self._sync_process is not None:
            self._sync_process.terminate()
            self._sync_process = None
        for handle in list(self._visa.values()):
            handle[0].close()

    def run(self):
        """Run server with asyncio runner"""
        asyncio.run(self._run())

    async def _run(self):
        """Async runner."""
        while not self._stop.is_set():
            polled = await self._socket.poll(100)
            if polled == 0:
                continue
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
        identity, _, request = msg
        job_data = pickle.loads(request)
        LOGGER.debug(f"Job {job_data} from {identity}")
        result = {}
        try:
            VALIDATOR.validate(job_data, schema)
            res = await self._execute_job(identity.decode(), job_data)
        except Exception as err:
            # Unfortunately, no simple and lightweight solution
            # https://stackoverflow.com/a/45241491
            LOGGER.error(f"Job {job_data} from {identity} threw {err}")
            result["exception"] = pickle.dumps(sys.exc_info())
        else:
            LOGGER.debug(f"Job {job_data} from {identity} result: {res}")
            result["value"] = res
        return [identity, b"", pickle.dumps(result)]

    async def _execute_job(
        self, identity: str, job_data: dict
    ) -> typing.Optional[typing.Any]:
        """Execute pyvisa job data.

        :return: Result data dictionary
        :rtype: dict or any base type
        """
        if job_data["action"] == "list_resources":
            res = await self._list_resources_wrapper(job_data)
        elif job_data["action"] == "open_resource":
            res = await self._open_resource_wrapper(identity, job_data)
        elif job_data["action"] == "close_resource":
            res = await self._close_resource_wrapper(identity, job_data)
        elif job_data["action"] == "getattr":
            res = await self._getattr_wrapper(identity, job_data)
        elif job_data["action"] == "setattr":
            res = await self._setattr_wrapper(identity, job_data)
        else:
            raise NotImplementedError("Action not supported.")
        return res

    async def _list_resources_wrapper(self, job_data):
        """Wrap list_resources call."""
        loop = asyncio.get_running_loop()
        args, kwargs = self._get_args_and_kwargs(job_data)
        instruments = await loop.run_in_executor(
            None, lambda: self._rm.list_resources(*args, **kwargs)
        )
        return instruments

    async def _open_resource_wrapper(self, identity: str, job_data: dict):
        """Wrap open_resource call."""
        args, kwargs = self._get_args_and_kwargs(job_data)
        await self._create_visa_handle(identity, *args, **kwargs)
        return ""

    async def _close_resource_wrapper(self, identity: str, job_data: dict):
        """Close a VISA handle and delete it from storate."""
        args, kwargs = self._get_args_and_kwargs(job_data)
        await self._delete_visa_handle(identity, *args, **kwargs)
        return ""

    async def _getattr_wrapper(self, identity: str, job_data: dict):
        """Wrap the getattr call."""
        loop = asyncio.get_running_loop()
        visa = await self._get_visa_handle(identity)
        attribute = await loop.run_in_executor(
            None, getattr, visa, job_data["name"]
        )
        if callable(attribute):

            def call():
                return attribute(*args, **kwargs)

            args, kwargs = self._get_args_and_kwargs(job_data)
            res = await loop.run_in_executor(None, call)
        else:
            res = attribute
        return res

    async def _setattr_wrapper(self, identity: str, job_data: dict):
        """Wrap the setattr call."""
        loop = asyncio.get_running_loop()
        visa = await self._get_visa_handle(identity)
        await loop.run_in_executor(
            None, setattr, visa, job_data["name"], job_data["value"]
        )
        res = None
        return res

    def _get_args_and_kwargs(self, job_data: dict):
        """Extract arguments and keyword arguments."""
        args = tuple(job_data.get("args", ()))
        kwargs = job_data.get("kwargs", {})
        return args, kwargs

    async def _get_visa_handle(self, identity: str) -> pyvisa.Resource:
        """Get VISA handle in an asyncio manner.

        :param resource: VISA information resource string
        :type resource: str
        :return: pyvisa resource handle
        :rtype: pyvisa.Resource
        """
        if identity not in self._visa:
            raise InvalidSession()
        self._visa[identity][1] = time.time()
        return self._visa[identity][0]

    async def _create_visa_handle(self, identity: str, *args, **kwargs):
        """Create a VISA handle with given resource, args and kwargs."""
        loop = asyncio.get_running_loop()
        or_kwargs = {}
        or_kwargs["access_mode"] = kwargs.pop(
            "access_mode", pyvisa.constants.AccessModes.no_lock
        )
        or_kwargs["open_timeout"] = kwargs.pop(
            "open_timeout", pyvisa.constants.VI_TMO_IMMEDIATE
        )
        or_kwargs["resource_pyclass"] = kwargs.pop("resource_pyclass", None)
        self._visa[identity] = [
            await loop.run_in_executor(
                None,
                lambda: self._rm.open_resource(*args, **or_kwargs),
            ),
            time.time(),
        ]
        for key, value in kwargs.items():
            await loop.run_in_executor(
                None, setattr, self._visa[identity], key, value
            )

    async def _delete_visa_handle(self, identity: str, *args, **kwargs):
        """Close a VISA handle and delete it from storage."""
        loop = asyncio.get_running_loop()
        handle = self._visa[identity][0]
        await loop.run_in_executor(
            None,
            handle.close,
        )
        del self._visa[identity]
