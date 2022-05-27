"""PyVISA-proxy server which provides access to VISA handles.

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
from abc import ABC, abstractmethod
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


class ProcessorInterface(ABC):
    """Interface class for processors."""

    @abstractmethod
    def close(self):
        """Close connections."""
        pass

    @abstractmethod
    async def call(self):
        """Specific call functions."""
        pass


class SynchronizationProcessor(ProcessorInterface):
    """Synchronization implementation class."""

    def __init__(
        self, sync_port: int, rpc_port: int, backend: str, version: str
    ):
        """Initialize processor."""
        self.ctx = zmq.asyncio.Context.instance()
        self.socket = self.ctx.socket(zmq.ROUTER)  # pylint: disable=E1101
        self.socket.bind(f"tcp://*:{sync_port}")
        self.port = sync_port
        self.rpc_port = rpc_port
        self.backend = backend
        self.version = version

    def close(self):
        """Close connections."""
        if self.socket:
            self.socket.close()

    async def call(self):
        """Process synchronization call."""
        address, _, _ = await self.socket.recv_multipart()
        reply = {
            "rpc_port": self.rpc_port,
            "backend": self.backend,
            "version": self.version,
        }
        await self.socket.send_multipart([address, b"", pickle.dumps(reply)])


class RpcProcessor(ProcessorInterface):
    """Synchronization implementation class."""

    def __init__(self, backend: str):
        """Initialize processor."""
        self.rm = pyvisa.ResourceManager(backend)
        self.visa: typing.Dict[str, list] = {}
        self.ctx = zmq.asyncio.Context.instance()
        self.socket = self.ctx.socket(zmq.ROUTER)  # pylint: disable=E1101
        self.port = self.socket.bind_to_random_port("tcp://*")

    def close(self):
        """Close connections."""
        for handle in list(self.visa.values()):
            handle[0].close()
        if self.socket:
            self.socket.close()

    async def call(self):
        """Process RPC call."""
        identity, _, request = await self.socket.recv_multipart()
        job_data = pickle.loads(request)
        LOGGER.debug(f"Job {job_data} from {identity}")
        reply = await self._call_pyvisa(identity, job_data)
        await self.socket.send_multipart([identity, b"", pickle.dumps(reply)])

    async def _call_pyvisa(self, identity: bytes, job_data: dict) -> dict:
        """Call pyvisa with job information from client.

        :param msg: job description message
        :type msg: zmq.Frage
        :return: Result data
        :rtype: zmq.Frame
        """
        result = {}
        try:
            VALIDATOR.validate(job_data, schema)
            res = await self._execute_job(identity.decode(), job_data)
        except Exception as err:
            # Unfortunately, no simple and lightweight solution
            # https://stackoverflow.com/a/45241491
            LOGGER.error(
                f"Job {job_data} from {identity.decode()} failedthrew {err}"
            )
            result["exception"] = pickle.dumps(sys.exc_info())
        else:
            LOGGER.debug(
                f"Job {job_data} from {identity.decode()} result: {res}"
            )
            result["value"] = res
        return result

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
            None, lambda: self.rm.list_resources(*args, **kwargs)
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
        if identity not in self.visa:
            raise InvalidSession()
        self.visa[identity][1] = time.time()
        return self.visa[identity][0]

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
        self.visa[identity] = [
            await loop.run_in_executor(
                None,
                lambda: self.rm.open_resource(*args, **or_kwargs),
            ),
            time.time(),
        ]
        for key, value in kwargs.items():
            await loop.run_in_executor(
                None, setattr, self.visa[identity], key, value
            )

    async def _delete_visa_handle(self, identity: str, *args, **kwargs):
        """Close a VISA handle and delete it from storage."""
        loop = asyncio.get_running_loop()
        handle = self.visa[identity][0]
        await loop.run_in_executor(
            None,
            handle.close,
        )
        del self.visa[identity]


class ProxyServer:
    """
    PyVISA remote proxy server which handles incoming VISA calls.

    :param object: object base class
    :type object: object
    """

    def __init__(self, port: int, backend: str = ""):
        """Initialize proxy server."""
        self._stop = Event()
        self._poller = zmq.Poller()
        self._rpc_processor: typing.Optional[RpcProcessor] = RpcProcessor(
            backend
        )
        self._sync_processor: typing.Optional[
            SynchronizationProcessor
        ] = SynchronizationProcessor(
            port, self._rpc_processor.port, backend, VERSION
        )
        self._poller.register(self._rpc_processor.socket, zmq.POLLIN)
        self._poller.register(self._sync_processor.socket, zmq.POLLIN)

    def __enter__(self):
        """Context manager initialization implementation."""
        return self

    def __exit__(self, exc_type, exc_value, trace):
        """Context manager close implementation."""
        self.close()

    def __del__(self):
        """Clean up."""
        self.close()

    def close(self):
        """Close sync-process, zmq connection and VISA handles."""
        self._stop.set()
        if hasattr(self, "_rpc_processor") and self._rpc_processor is not None:
            self._rpc_processor.close()
            self._rpc_processor = None
        if (
            hasattr(self, "_sync_processor")
            and self._sync_processor is not None
        ):
            self._sync_processor.close()
            self._sync_processor = None

    def run(self) -> None:
        """Run server with asyncio runner."""
        LOGGER.info("Starting PyVISA Proxy Server.")
        LOGGER.info(f"PyVISA-proxy version: {VERSION}")
        backend = typing.cast(
            SynchronizationProcessor, self._sync_processor
        ).backend
        if backend != "":
            LOGGER.info(f"PyVISA backend: {backend}")
        sync_port = typing.cast(
            SynchronizationProcessor, self._sync_processor
        ).port
        LOGGER.info(f"Synchronization port: " f"{sync_port}")
        LOGGER.info(
            f"RPC port: {typing.cast(RpcProcessor, self._rpc_processor).port}"
        )
        asyncio.run(self._run())

    async def _run(self):
        """Async runner."""
        while not self._stop.is_set():
            socks = dict(self._poller.poll(100))
            if (
                typing.cast(
                    SynchronizationProcessor, self._sync_processor
                ).socket
                in socks
                and socks[
                    typing.cast(
                        SynchronizationProcessor, self._sync_processor
                    ).socket
                ]
                == zmq.POLLIN
            ):
                await typing.cast(
                    SynchronizationProcessor, self._sync_processor
                ).call()
            if (
                typing.cast(RpcProcessor, self._rpc_processor).socket in socks
                and socks[
                    typing.cast(RpcProcessor, self._rpc_processor).socket
                ]
                == zmq.POLLIN
            ):
                await typing.cast(RpcProcessor, self._rpc_processor).call()
