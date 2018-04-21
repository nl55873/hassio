"""DBus implementation with glib."""
import asyncio
import logging
import shlex
import xml.etree.ElementTree as ET

_LOGGER = logging.getLogger(__name__)

INTROSPECT = ("gdbus introspect --system --dest {bus} "
              "--object-path {obj} --xml")
CALL = ("gdbus call --system --dest {bus} --object-path {obj} "
        "--method {obj}.{method} {args}")


class DBusError(Exception):
    """DBus generic error."""
    pass


class DBusFatalError(DBusError):
    """DBus call going wrong."""
    pass


class DBusReturnError(DBusError):
    """DBus return error."""
    pass


class DBusParseError(DBusError):
    """DBus parse error."""
    pass


class DBus(object):
    """DBus handler."""

    def __init__(self, bus_name, object_path):
        """Initialize dbus object."""
        self.bus_name = bus_name
        self.object_path = object_path
        self.methods = []

    @staticmethod
    async def connect(bus_name, object_path):
        """Read object data."""
        self = DBus(bus_name, object_path)
        self._init_proxy()  # pylint: disable=protected-access

        _LOGGER.info("Connect to dbus: %s", bus_name)
        return self

    async def _init_proxy(self):
        """Read object data."""
        command = shlex.split(INTROSPECT.format(
            bus=self.bus_name,
            obj=self.object_path
        ))

        # Ask data
        try:
            data = await self._send(command)
        except DBusError:
            _LOGGER.error(
                "DBus fails connect to %s", self.object_path)
            raise

        # Parse XML
        try:
            xml = ET.fromstring(data)
        except ET.ParseError as err:
            _LOGGER.error("Can't parse introspect data: %s", err)
            raise DBusParseError() from None

        # Read available methods
        for method in xml.findall(".//method"):
            self.methods.append(method.get('name'))

    @staticmethod
    def _gvariant(raw):
        """Parse GVariant input to python."""
        return raw

    async def _call_dbus(self, method, *args):
        """Call a dbus method."""
        command = shlex.split(CALL.format(
            bus=self.bus_name,
            obj=self.object_path,
            method=method,
            args=" ".join(map(str, args))
        ))

        # Run command
        try:
            data = await self._send(command)
        except DBusError:
            _LOGGER.error(
                "DBus fails with %s on %s", method, self.object_path)
            raise

        # Parse and return data
        return self._gvariant(data)

    async def _send(self, command):
        """Send command over dbus."""
        # Run command
        try:
            proc = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )

            data, _ = await proc.communicate()
        except OSError as err:
            _LOGGER.error("DBus fatal error: %s", err)
            raise DBusFatalError() from None

        # Success?
        if proc.returncode != 0:
            raise DBusReturnError()

        # End
        return data.decode()

    def __getattr__(self, name):
        """Mapping to dbus method."""
        if name not in self.methods:
            raise AttributeError()

        def _method_wrapper(*args):
            """Wrap method.

            Return a coroutine
            """
            return self._call_dbus(name, *args)

        return _method_wrapper
