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
from autotest_lib.client.cros import cros_ui
from autotest_lib.client.cros import tpm_store

# pylint: disable=W0611
from autotest_lib.client.cros import flimflam_test_path
# pylint: enable=W0611
import wifi_proxy


class ShillXmlRpcDelegate(xmlrpc_server.XmlRpcDelegate):
    """Exposes methods called remotely during WiFi autotests.

    All instance methods of this object without a preceding '_' are exposed via
    an XMLRPC server.  This is not a stateless handler object, which means that
    if you store state inside the delegate, that state will remain around for
    future calls.

    """

    def __init__(self):
        self._wifi_proxy = wifi_proxy.WifiProxy()
        self._tpm_store = tpm_store.TPMStore()


    def __enter__(self):
        super(ShillXmlRpcDelegate, self).__enter__()
        self._tpm_store.__enter__()


    def __exit__(self, exception, value, traceback):
        super(ShillXmlRpcDelegate, self).__exit__(exception, value, traceback)
        self._tpm_store.__exit__(exception, value, traceback)
        self.enable_ui()


    @xmlrpc_server.dbus_safe(False)
    def create_profile(self, profile_name):
        """Create a shill profile.

        @param profile_name string name of profile to create.
        @return True on success, False otherwise.

        """
        self._wifi_proxy.manager.CreateProfile(profile_name)
        return True


    @xmlrpc_server.dbus_safe(False)
    def push_profile(self, profile_name):
        """Push a shill profile.

        @param profile_name string name of profile to push.
        @return True on success, False otherwise.

        """
        self._wifi_proxy.manager.PushProfile(profile_name)
        return True


    @xmlrpc_server.dbus_safe(False)
    def pop_profile(self, profile_name):
        """Pop a shill profile.

        @param profile_name string name of profile to pop.
        @return True on success, False otherwise.

        """
        if profile_name is None:
            self._wifi_proxy.manager.PopAnyProfile()
        else:
            self._wifi_proxy.manager.PopProfile(profile_name)
        return True


    @xmlrpc_server.dbus_safe(False)
    def remove_profile(self, profile_name):
        """Remove a profile from disk.

        @param profile_name string name of profile to remove.
        @return True on success, False otherwise.

        """
        self._wifi_proxy.manager.RemoveProfile(profile_name)
        return True


    @xmlrpc_server.dbus_safe(False)
    def clean_profiles(self):
        """Pop and remove shill profiles above the default profile.

        @return True on success, False otherwise.

        """
        while True:
            active_profile = self._wifi_proxy.get_active_profile()
            profile_name = self._wifi_proxy.dbus2primitive(
                    active_profile.GetProperties(utf8_strings=True)['Name'])
            if profile_name == 'default':
                return True
            self._wifi_proxy.manager.PopProfile(profile_name)
            self._wifi_proxy.manager.RemoveProfile(profile_name)


    def connect_wifi(self, raw_params):
        """Block and attempt to connect to wifi network.

        @param raw_params serialized AssociationParameters.
        @return serialized AssociationResult

        """
        logging.debug('connect_wifi()')
        params = xmlrpc_datatypes.deserialize(raw_params)
        params.security_config.install_client_credentials(self._tpm_store)
        raw = self._wifi_proxy.connect_to_wifi_network(
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
        result = self._wifi_proxy.disconnect_from_wifi_network(ssid)
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

        return self._wifi_proxy.configure_bgscan(
                params.interface,
                method=params.method,
                short_interval=params.short_interval,
                long_interval=params.long_interval,
                signal=params.signal)


    def wait_for_service_states(self, ssid, states, timeout_seconds):
        """Wait for service to achieve one state out of a list of states.

        @param ssid string the network to connect to (e.g. 'GoogleGuest').
        @param states tuple the states for which to wait
        @param timeout_seconds int seconds to wait for a state

        """
        return self._wifi_proxy.wait_for_service_states(
                ssid, states, timeout_seconds)


    @xmlrpc_server.dbus_safe(None)
    def get_service_properties(self, ssid):
        """Get a dict of properties for a service.

        @param ssid string service to get properties for.
        @return dict of Python friendly native types or None on failures.

        """
        discovery_params = {self._wifi_proxy.SERVICE_PROPERTY_TYPE: 'wifi',
                            self._wifi_proxy.SERVICE_PROPERTY_NAME: ssid}
        service_path = self._wifi_proxy.manager.FindMatchingService(
                discovery_params)
        service_object = self._wifi_proxy.get_dbus_object(
                self._wifi_proxy.DBUS_TYPE_SERVICE, service_path)
        service_properties = service_object.GetProperties(
                utf8_strings=True)
        return self._wifi_proxy.dbus2primitive(service_properties)


    def disable_ui(self):
        """@return True iff the UI is off when we return."""
        return cros_ui.stop()


    def enable_ui(self):
        """@return True iff the UI was successfully started."""
        return cros_ui.start()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    handler = logging.handlers.SysLogHandler(address = '/dev/log')
    logging.getLogger().addHandler(handler)
    logging.debug('shill_xmlrpc_server main...')
    server = xmlrpc_server.XmlRpcServer('localhost',
                                         constants.SHILL_XMLRPC_SERVER_PORT)
    server.register_delegate(ShillXmlRpcDelegate())
    server.run()
