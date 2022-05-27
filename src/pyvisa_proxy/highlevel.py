"""Remote VISA Library.

:copyright: 2022 by PyVISA-proxy Authors, see AUTHORS for more details.
:license: MIT, see LICENSE for more details.
"""

import logging
import platform
import random
import typing
import uuid
from collections import OrderedDict

import dill as pickle
import pyvisa.errors as errors
import zmq
from packaging.version import parse
from pyvisa import Resource, constants, highlevel
from pyvisa.constants import StatusCode
from pyvisa.typing import VISASession
from pyvisa.util import LibraryPath

from .ProxyResource import ProxyResource
from .RpcClient import RpcClient
from .version import get_version

# This import is required to register subclasses


VERSION = get_version()
LOGGER = logging.getLogger(__name__)


class CompatibilityError(Exception):
    """Compatibility exception class."""

    pass


def sync_up(host: str, sync_port: int, timeout: int):
    """Synchronize with Proxy server."""
    ctx = zmq.Context.instance()
    socket = ctx.socket(zmq.REQ)  # pylint: disable=E1101
    socket.identity = f"{platform.node()}.{uuid.uuid4()}".encode()
    socket.connect(f"tcp://{host}:{sync_port}")
    try:
        socket.send(b"")
        polled = socket.poll(timeout=timeout * 1000)
        if polled == 0:
            raise TimeoutError(
                "Establishing a connection to PyVISA proxy timed out."
            )
        reply = pickle.loads(socket.recv())
        return (
            reply.get("rpc_port"),
            reply.get("backend"),
            reply.get("version"),
        )
    finally:
        socket.close()


def check_for_version_compatibility(version):
    """Check for a client and server version compabitility."""
    resource_version = parse(VERSION)
    server_version = parse(version)
    if resource_version.release < server_version.release:
        raise CompatibilityError(
            f"Proxy server version {version} is to great."
        )


class ProxyVisaLibrary(highlevel.VisaLibraryBase):
    """A pure Python backend for PyVISA.

    The object is basically a dispatcher with some common functions
    implemented.

    When a new resource object is requested to pyvisa, the library creates a
    Session object (that knows how to perform low-level communication
    operations) associated with a session handle (a number, usually refered
    just as session).

    A call to a library function is handled by PyVisaLibrary if it involves
    a resource agnostic function or dispatched to the correct session
    object (obtained from the session id).

    Importantly, the user is unaware of this. PyVisaLibrary behaves for the
    user just as NIVisaLibrary.
    """

    def __del__(self):
        """Clean up on garbage collection."""
        rpc_client = getattr(self, "_rpc_client", None)
        if rpc_client is not None:
            rpc_client.close()

    @staticmethod
    def get_library_paths():
        """List a dummy library path to allow to create the library."""
        return (LibraryPath("unset"),)

    def get_debug_info(self):
        """Return a list of lines with backend info."""
        from . import __version__

        d = OrderedDict()
        d["Version"] = "%s" % __version__

        return d

    def _init(self):

        #: map session handle to session object.
        self.sessions = {}
        try:
            self._rpc_host, self._rpc_sync_port = self.library_path.split(":")
        except Exception:
            raise ValueError("No proxy host and port set.")
        self._rpc_port, self._proxy_backend, self._proxy_version = sync_up(
            self._rpc_host, self._rpc_sync_port, 2
        )
        check_for_version_compatibility(self._proxy_version)
        self._rpc_client = RpcClient(self._rpc_host, self._rpc_port)

    def _register(self, obj):
        """Create a random but unique session handle for a session object.

        Register it in the sessions dictionary and return the value

        :param obj: a session object.
        :return: session handle
        :rtype: int
        """
        session = None

        while session is None or session in self.sessions:
            session = random.randint(1000000, 9999999)

        self.sessions[session] = obj
        return session

    def open(
        self,
        session,
        resource_name,
        access_mode=constants.AccessModes.no_lock,
        open_timeout=constants.VI_TMO_IMMEDIATE,
    ) -> typing.Tuple[VISASession, StatusCode]:
        """Open a session to the specified resource.

        Corresponds to viOpen function of the VISA library.

        :param session: Resource Manager session
                        (should always be a session returned
                        from open_default_resource_manager()).
        :param resource_name: Unique symbolic name of a resource.
        :param access_mode: Specifies the mode by which the resource is to be
                            accessed. (constants.AccessModes)
        :param open_timeout: Specifies the maximum time period
                            (in milliseconds) that this operation waits
                            before returning an error.
        :return: Unique logical identifier reference to a session, return value
                            of the library call.
        :rtype: session, :class:`pyvisa.constants.StatusCode`
        """
        # Do not support it currently
        raise NotImplementedError(
            "Opening a bare resource remotely is currently not suported. \
            Planned for version 0.2.0"
        )

    def open_resource(
        self,
        resource_name: str,
        access_mode: constants.AccessModes = constants.AccessModes.no_lock,
        open_timeout: int = constants.VI_TMO_IMMEDIATE,
        resource_pyclass: typing.Optional[typing.Type["Resource"]] = None,
        **kwargs: typing.Any,
    ) -> typing.Type["Resource"]:
        """Return an instrument for the resource name.

        Parameters
        ----------
        resource_name : str
            Name or alias of the resource to open.
        access_mode : constants.AccessModes, optional
            Specifies the mode by which the resource is to be accessed,
            by default constants.AccessModes.no_lock
        open_timeout : int, optional
            If the ``access_mode`` parameter requests a lock, then this
            parameter specifies the absolute time period (in milliseconds) that
            the resource waits to get unlocked before this operation returns an
            error, by default constants.VI_TMO_IMMEDIATE.
        resource_pyclass : Optional[Type[Resource]], optional
            Resource Python class to use to instantiate the Resource.
            Defaults to None: select based on the resource name.
        kwargs : Any
            Keyword arguments to be used to change instrument attributes
            after construction.

        Returns
        -------
        Resource
            Subclass of Resource matching the resource.

        """
        kwargs["access_mode"] = access_mode
        kwargs["open_timeout"] = open_timeout
        kwargs["resource_pyclass"] = resource_pyclass

        res = ProxyResource(
            resource_pyclass,
            resource_name,
            self._rpc_host,
            self._rpc_port,
            **kwargs,
        )
        return res

    def close(self, session):
        """Close the specified session, event, or find list.

        Corresponds to viClose function of the VISA library.

        :param session: Unique logical identifier to a session, event, or
            find list.
        :return: return value of the library call.
        :rtype: :class:`pyvisa.constants.StatusCode`
        """
        try:
            del self.sessions[session]
            return constants.StatusCode.success
        except KeyError:
            return constants.StatusCode.error_invalid_object

    def open_default_resource_manager(self):
        """Return a session to the Default Resource Manager resource.

        Corresponds to viOpenDefaultRM function of the VISA library.

        :return: Unique logical identifier to a Default Resource Manager
            session, return value of the library call.
        :rtype: session, :class:`pyvisa.constants.StatusCode`
        """
        return self._register(self), constants.StatusCode.success

    def list_resources(self, session, query="?*::INSTR"):
        """Return a tuple of all connected devices matching query.

        :param session:
        :param query: regular expression used to match devices.
        """
        return self._rpc_client.request(
            None,
            "list_resources",
            kwargs={"query": query},
        )

    def read(self, session, count):
        """Read data from device or interface synchronously.

        Corresponds to viRead function of the VISA library.

        :param session: Unique logical identifier to a session.
        :param count: Number of bytes to be read.
        :return: data read, return value of the library call.
        :rtype: bytes, :class:`pyvisa.constants.StatusCode`
        """
        try:
            sess = self.sessions[session]
        except KeyError:
            return b"", constants.StatusCode.error_invalid_object

        try:
            chunk, status = sess.read(count)
            if status == constants.StatusCode.error_timeout:
                raise errors.VisaIOError(constants.VI_ERROR_TMO)
            return chunk, status
        except AttributeError:
            return b"", constants.StatusCode.error_nonsupported_operation

    def write(self, session, data):
        """Write data to device or interface synchronously.

        Corresponds to viWrite function of the VISA library.

        :param session: Unique logical identifier to a session.
        :param data: data to be written.
        :type data: str
        :return: Number of bytes actually transferred, return value of the
            library call.
        :rtype: int, :class:`pyvisa.constants.StatusCode`
        """
        try:
            sess = self.sessions[session]
        except KeyError:
            return 0, constants.StatusCode.error_invalid_object

        try:
            return sess.write(data)
        except AttributeError:
            return 0, constants.StatusCode.error_nonsupported_operation

    def get_attribute(self, session, attribute):
        """Retrieve the state of an attribute.

        Corresponds to viGetAttribute function of the VISA library.

        :param session: Unique logical identifier to a session, event, or
            find list.
        :param attribute: Resource attribute for which the state query is
            made (see Attributes.*)
        :return: The state of the queried attribute for a specified resource,
            return value of the library call.
        :rtype: unicode (Py2) or str (Py3), list or other type,
            :class:`pyvisa.constants.StatusCode`
        """
        try:
            sess = self.sessions[session]
        except KeyError:
            return 0, constants.StatusCode.error_invalid_object

        return sess.get_attribute(attribute)

    def set_attribute(self, session, attribute, attribute_state):
        """Set the state of an attribute.

        Corresponds to viSetAttribute function of the VISA library.

        :param session: Unique logical identifier to a session.
        :param attribute: Attribute for which the state is to be
            modified. (Attributes.*)
        :param attribute_state: The state of the attribute to be set
            for the specified object.
        :return: return value of the library call.
        :rtype: :class:`pyvisa.constants.StatusCode`
        """
        try:
            sess = self.sessions[session]
        except KeyError:
            return constants.StatusCode.error_invalid_object

        return sess.set_attribute(attribute, attribute_state)
