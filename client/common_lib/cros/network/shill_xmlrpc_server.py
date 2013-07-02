#!/usr/bin/python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import logging.handlers

import common
from autotest_lib.client.common_lib.cros import xmlrpc_server
from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.client.cros import constants
from autotest_lib.client.cros import tpm_store

# pylint: disable=W0611
from autotest_lib.client.cros import flimflam_test_path
# pylint: enable=W0611
import shill_proxy


class ShillXmlRpcDelegate(xmlrpc_server.XmlRpcDelegate):
    """Exposes methods called remotely during WiFi autotests.

    All instance methods of this object without a preceding '_' are exposed via
    an XMLRPC server.  This is not a stateless handler object, which means that
    if you store state inside the delegate, that state will remain around for
    future calls.

    """

    def __init__(self):
        self._shill_proxy = shill_proxy.ShillProxy()
        self._tpm_store = tpm_store.TPMStore()


    def __enter__(self):
        super(ShillXmlRpcDelegate, self).__enter__()
        self._tpm_store.__enter__()


    def __exit__(self, exception, value, traceback):
        super(ShillXmlRpcDelegate, self).__exit__(exception, value, traceback)
        self._tpm_store.__exit__(exception, value, traceback)


    @xmlrpc_server.dbus_safe(False)
    def create_profile(self, profile_name):
        """Create a shill profile.

        @param profile_name string name of profile to create.
        @return True on success, False otherwise.

        """
        self._shill_proxy.manager.CreateProfile(profile_name)
        return True


    @xmlrpc_server.dbus_safe(False)
    def push_profile(self, profile_name):
        """Push a shill profile.

        @param profile_name string name of profile to push.
        @return True on success, False otherwise.

        """
        self._shill_proxy.manager.PushProfile(profile_name)
        return True


    @xmlrpc_server.dbus_safe(False)
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


    @xmlrpc_server.dbus_safe(False)
    def remove_profile(self, profile_name):
        """Remove a profile from disk.

        @param profile_name string name of profile to remove.
        @return True on success, False otherwise.

        """
        self._shill_proxy.manager.RemoveProfile(profile_name)
        return True


    @xmlrpc_server.dbus_safe(False)
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
        params = xmlrpc_datatypes.deserialize(raw_params)
        params.security_config.install_client_credentials(self._tpm_store)
        raw = self._shill_proxy.connect_to_wifi_network(
                params.ssid,
                params.security,
                params.security_parameters,
                params.save_credentials,
                station_type=params.station_type,
                hidden_network=params.is_hidden,
                discovery_timeout_seconds=params.discovery_timeout,
                association_timeout_seconds=params.association_timeout,
                configuration_timeout_seconds=params.configuration_timeout)
        result = xmlrpc_datatypes.AssociationResult.from_dbus_proxy_output(raw)
        return result


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


    @xmlrpc_server.dbus_safe(False)
    def configure_bgscan(self, raw_params):
        """Configure background scan parameters via shill.

        @param raw_params serialized BgscanConfiguration.

        """
        params = xmlrpc_datatypes.deserialize(raw_params)
        if params.interface is None:
            logging.error('No interface specified to set bgscan parameters on.')
            return False

        return self._shill_proxy.configure_bgscan(
                params.interface,
                method=params.method,
                short_interval=params.short_interval,
                long_interval=params.long_interval,
                signal=params.signal)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    handler = logging.handlers.SysLogHandler(address = '/dev/log')
    logging.getLogger().addHandler(handler)
    logging.debug('shill_xmlrpc_server main...')
    server = xmlrpc_server.XmlRpcServer('localhost',
                                         constants.SHILL_XMLRPC_SERVER_PORT)
    server.register_delegate(ShillXmlRpcDelegate())
    server.run()
