"""
PyVISA-proxy server which provides access to VISA handles
"""
import sys
import pickle
import asyncio
import logging
import typing
import os
import json
import pyvisa
import msgpack
import zmq
import zmq.asyncio
from jsonschema import validate
from tblib import pickling_support
pickling_support.install()

LOGGER = logging.getLogger(__name__)

with open(os.path.abspath(os.path.join(os.path.dirname(__file__),
                                       'data', 'job.schema.json')), 'r',
          encoding='utf-8') as fp:
    schema = json.load(fp)


class RemoteServer:
    """
    pyvisa remote proxy server which handles incoming VISA calls

    :param object: object base class
    :type object: object
    """

    def __init__(self, port, ctx: typing.Optional[zmq.asyncio.Context] = None):
        self.ctx = ctx or zmq.asyncio.Context.instance()
        self._socket = self.ctx.socket(zmq.REP)
        self._socket.bind(f'tcp://*:{port}')
        self._visa_handle: dict = {}
        self._lock = asyncio.Lock()
        try:
            self._rm = pyvisa.ResourceManager()
        except Exception:
            self._rm = pyvisa.ResourceManager('@py')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, trace):
        self.close()

    def __del__(self):
        self.close()

    def close(self):
        """Close zmq connection and VISA handles"""
        if self._socket.is_open():
            self._socket.close()
        self.ctx.term()
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
        """
        Call pyvisa with job information from client

        :param msg: job description message
        :type msg: zmq.Frage
        :return: Result data
        :rtype: zmq.Frame
        """
        address, _, request = msg
        job_data = msgpack.loads(request)
        result = {}
        try:
            validate(job_data, schema)
            res = await self._execute_job(job_data)
        except Exception:
            # Unfortunately, no simple and lightweight solution
            # https://stackoverflow.com/a/45241491
            result['exception'] = pickle.dumps(sys.exc_info())
        else:
            result['value'] = res
        return [address, b"", msgpack.dumps(result)]

    async def _execute_job(self, job_data: dict) -> \
            typing.Optional[typing.Any]:
        """
        Execute pyvisa job data

        :return: Result data dictionary
        :rtype: dict or any base type
        """
        visa = await self._get_visa_handle(job_data['resource'])
        if job_data['action'] == '__getattr__':
            attribute = getattr(visa, job_data['name'])
            if callable(attribute):
                args = tuple([x for x in job_data['args']
                             if x is not None]) if job_data['args'] else ()
                kwargs = job_data['kwargs'] if job_data['kwargs'] else {}
                res = attribute(*args, **kwargs)
            else:
                res = attribute
        else:
            setattr(visa, job_data['name'], job_data['value'])
            res = None
        return res

    async def _get_visa_handle(self, resource: str) -> pyvisa.Resource:
        """
        Get VISA handle in an asyncio manner. Returns

        :param resource: VISA information resource string
        :type resource: str
        :return: pyvisa resource handle
        :rtype: pyvisa.Resource
        """
        if resource in self._visa_handle:
            return self._visa_handle[resource]
        async with self._lock:
            self._visa_handle[resource] = self._rm.open_resource(resource)
        return self._visa_handle[resource]
