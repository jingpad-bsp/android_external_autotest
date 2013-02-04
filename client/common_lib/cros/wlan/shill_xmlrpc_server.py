#!/usr/bin/python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import errno
import functools
import logging
import logging.handlers
import select
import signal
import threading
import SimpleXMLRPCServer

import common
from autotest_lib.client.common_lib.cros.wlan import xmlrpc_datatypes
from autotest_lib.client.cros import constants

# pylint: disable=W0611
from autotest_lib.client.cros import flimflam_test_path
# pylint: enable=W0611
import shill_proxy


def dbus_safe(default_return_value):
    """Catch all DBus exceptions and return a default value instead.

    Wrap a function with a try block that catches DBus exceptions and
    returns default instead.  This is convenient for simple error
    handling since XMLRPC doesn't understand DBus exceptions.

    @param wrapped_function function to wrap.
    @param default_return_value value to return on exception (usually False).

    """
    def decorator(wrapped_function):
        """Call a function and catch DBus errors.

        @param wrapped_function function to call in dbus safe context.
        @return function return value or default_return_value on failure.

        """
        @functools.wraps(wrapped_function)
        def wrapper(*args, **kwargs):
            """Pass args and kwargs to a dbus safe function.

            @param args formal python arguments.
            @param kwargs keyword python arguments.
            @return function return value or default_return_value on failure.

            """
            logging.debug('%s()', wrapped_function.__name__)
            try:
                return wrapped_function(*args, **kwargs)

            except dbus.exceptions.DBusException as e:
                logging.error('Exception while performing operation %s: %s: %s',
                              wrapped_function.__name__,
                              e.get_dbus_name(),
                              e.get_dbus_message())
                return default_return_value

        return wrapper

    return decorator


class ShillXmlRpcDelegate(object):
    """Exposes methods called remotely during WiFi autotests.

    All instance methods of this object without a preceding '_' are exposed via
    an XMLRPC server.  This is not a stateless handler object, which means that
    if you store state inside the delegate, that state will remain around for
    future calls.

    """

    def __init__(self):
        self._shill_proxy = shill_proxy.ShillProxy()


    @dbus_safe(False)
    def create_profile(self, profile_name):
        """Create a shill profile.

        @param profile_name string name of profile to create.
        @return True on success, False otherwise.

        """
        self._shill_proxy.manager.CreateProfile(profile_name)
        return True


    @dbus_safe(False)
    def push_profile(self, profile_name):
        """Push a shill profile.

        @param profile_name string name of profile to push.
        @return True on success, False otherwise.

        """
        self._shill_proxy.manager.PushProfile(profile_name)
        return True


    @dbus_safe(False)
    def pop_profile(self, profile_name):
        """Pop a shill profile.

        @param profile_name string name of profile to pop.
        @return True on success, False otherwise.

        """
        if profile_name is None:
            self._shill_proxy.manager.PopAnyProfile()
        else:
            self._shill_proxy.manager.PopProfile(profile_name)
        return True


    @dbus_safe(False)
    def remove_profile(self, profile_name):
        """Remove a profile from disk.

        @param profile_name string name of profile to remove.
        @return True on success, False otherwise.

        """
        self._shill_proxy.manager.RemoveProfile(profile_name)
        return True


    @dbus_safe(False)
    def clean_profiles(self):
        """Pop and remove shill profiles above the default profile.

        @return True on success, False otherwise.

        """
        while True:
            active_profile = self._shill_proxy.get_active_profile()
            profile_name = shill_proxy.dbus2primitive(
                    active_profile.GetProperties(utf8_strings=True)['Name'])
            if profile_name == 'default':
                return True
            self._shill_proxy.manager.PopProfile(profile_name)
            self._shill_proxy.manager.RemoveProfile(profile_name)


    def connect_wifi(self, raw_params):
        """Block and attempt to connect to wifi network.

        @param raw_params serialized AssociationParameters.
        @return serialized AssociationResult

        """
        logging.debug('connect_wifi()')
        params = xmlrpc_datatypes.AssociationParameters(raw_params)
        result = xmlrpc_datatypes.AssociationResult.\
                from_dbus_proxy_output(
                        self._shill_proxy.connect_to_wifi_network(
                                params.ssid,
                                params.security,
                                params.psk,
                                params.save_credentials,
                                params.discovery_timeout,
                                params.association_timeout,
                                params.configuration_timeout))
        return result.serialize()


    def disconnect(self, ssid):
        """Attempt to disconnect from the given ssid.

        Blocks until disconnected or operation has timed out.  Returns True iff
        disconnect was successful.

        @param ssid string network to disconnect from.
        @return bool True on success, False otherwise.

        """
        logging.debug('disconnect()')
        result = self._shill_proxy.disconnect_from_wifi_network(ssid)
        successful, duration, message = result
        if successful:
            level = logging.info
        else:
            level = logging.error
        level('Disconnect result: %r, duration: %d, reason: %s',
              successful, duration, message)
        return successful is True


    def ready(self):
        """Confirm that the XMLRPC server is up and ready to serve."""
        logging.debug('ready()')
        return True


class ShillXmlRpcServer(threading.Thread):
    """Simple XMLRPC server implementation.

    In theory, Python should provide a sane XMLRPC server implementation as
    part of its standard library.  In practice the provided implementation
    doesn't handle signals, not even EINTR.  As a result, we have this class.

    Usage:

    server = ShillXmlRpcServer(('localhost', 43212))
    server.run()

    """
    def __init__(self, addr=None):
        """Construct a ShillXmlRpcServer.

        @param addr tuple of (string ip adresss, int local port number).

        """
        super(ShillXmlRpcServer, self).__init__()
        self._delegate = ShillXmlRpcDelegate()
        if addr is None:
            addr = ('localhost', constants.SHILL_XMLRPC_SERVER_PORT)
        logging.info('Binding server to %s', addr)
        self._server = SimpleXMLRPCServer.SimpleXMLRPCServer(addr)
        self._server.register_introspection_functions()
        self._server.register_instance(self._delegate)
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
        self._keep_running = True


    def run(self):
        """Block and handle many XmlRpc requests."""
        logging.info("ShillXmlRpcServer starting...")
        while self._keep_running:
            try:
                self._server.handle_request()
            except select.error as v:
                # In a cruel twist of fate, the python library doesn't handle
                # this kind of error.
                if v[0] != errno.EINTR:
                    raise
        logging.info("ShillXmlRpcServer exited.")


    def _handle_signal(self, _signum, _frame):
        """Handle a process signal by gracefully quitting.

        SimpleXMLRPCServer helpfully exposes a method called shutdown() which
        clears a flag similar to _keep_running, and then blocks until it sees
        the server shut down.  Unfortunately, if you call that function from
        a signal handler, the server will just hang, since the process is
        paused for the signal, causing a deadlock.  Thus we are reinventing the
        wheel.

        """
        self._keep_running = False


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    handler = logging.handlers.SysLogHandler(address = '/dev/log')
    logging.getLogger().addHandler(handler)
    logging.debug('shill_xmlrpc_server main...')
    ShillXmlRpcServer().run()
