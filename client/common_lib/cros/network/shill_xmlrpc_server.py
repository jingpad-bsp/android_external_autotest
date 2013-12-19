#!/usr/bin/python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import logging.handlers
import multiprocessing

import common
from autotest_lib.client.common_lib import utils
from autotest_lib.client.common_lib.cros import xmlrpc_server
from autotest_lib.client.common_lib.cros.network import iw_runner
from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.client.cros import constants
from autotest_lib.client.cros import cros_ui
from autotest_lib.client.cros import sys_power
from autotest_lib.client.cros import tpm_store
from autotest_lib.client.cros.networking import shill_proxy
from autotest_lib.client.cros.networking import wifi_proxy



class ShillXmlRpcDelegate(xmlrpc_server.XmlRpcDelegate):
    """Exposes methods called remotely during WiFi autotests.

    All instance methods of this object without a preceding '_' are exposed via
    an XMLRPC server.  This is not a stateless handler object, which means that
    if you store state inside the delegate, that state will remain around for
    future calls.

    """

    DEFAULT_TEST_PROFILE_NAME = 'test'
    ROAM_THRESHOLD = 'RoamThreshold'
    DBUS_DEVICE = 'Device'

    def __init__(self):
        self._wifi_proxy = wifi_proxy.WifiProxy()
        self._tpm_store = tpm_store.TPMStore()


    def __enter__(self):
        super(ShillXmlRpcDelegate, self).__enter__()
        if not cros_ui.stop(allow_fail=True):
            logging.error('UI did not stop, there could be trouble ahead.')
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


    @xmlrpc_server.dbus_safe(False)
    def configure_service_by_guid(self, raw_params):
        """Configure a service referenced by a GUID.

        @param raw_params serialized ConfigureServiceParameters.

        """
        params = xmlrpc_datatypes.deserialize(raw_params)
        shill = self._wifi_proxy
        properties = {}
        if params.autoconnect is not None:
            properties[shill.SERVICE_PROPERTY_AUTOCONNECT] = params.autoconnect
        if params.passphrase is not None:
            properties[shill.SERVICE_PROPERTY_PASSPHRASE] = params.passphrase
        if properties:
            self._wifi_proxy.configure_service_by_guid(params.guid, properties)
        return True


    @xmlrpc_server.dbus_safe(False)
    def configure_wifi_service(self, raw_params):
        """Configure a WiFi service

        @param raw_params serialized AssociationParameters.
        @return True on success, False otherwise.

        """
        params = xmlrpc_datatypes.deserialize(raw_params)
        return self._wifi_proxy.configure_wifi_service(
                params.ssid,
                params.security,
                params.security_parameters,
                save_credentials=params.save_credentials,
                station_type=params.station_type,
                hidden_network=params.is_hidden,
                guid=params.guid,
                autoconnect=params.autoconnect)


    def connect_wifi(self, raw_params):
        """Block and attempt to connect to wifi network.

        @param raw_params serialized AssociationParameters.
        @return serialized AssociationResult

        """
        logging.debug('connect_wifi()')
        params = xmlrpc_datatypes.deserialize(raw_params)
        params.security_config.install_client_credentials(self._tpm_store)
        wifi_if = params.bgscan_config.interface
        if wifi_if is None:
            logging.info('Using default interface for bgscan configuration')
            interfaces = iw_runner.IwRunner().list_interfaces()
            if not interfaces:
                return xmlrpc_datatypes.AssociationResult(
                        failure_reason='No wifi interfaces found?')

            if len(interfaces) > 1:
                logging.error('Defaulting to first interface of %r', interfaces)
            wifi_if = interfaces[0]
        if not self._wifi_proxy.configure_bgscan(
                wifi_if,
                method=params.bgscan_config.method,
                short_interval=params.bgscan_config.short_interval,
                long_interval=params.bgscan_config.long_interval,
                signal=params.bgscan_config.signal):
            return xmlrpc_datatypes.AssociationResult(
                    failure_reason='Failed to configure bgscan')

        raw = self._wifi_proxy.connect_to_wifi_network(
                params.ssid,
                params.security,
                params.security_parameters,
                params.save_credentials,
                station_type=params.station_type,
                hidden_network=params.is_hidden,
                guid=params.guid,
                discovery_timeout_seconds=params.discovery_timeout,
                association_timeout_seconds=params.association_timeout,
                configuration_timeout_seconds=params.configuration_timeout)
        result = xmlrpc_datatypes.AssociationResult.from_dbus_proxy_output(raw)
        return result


    @xmlrpc_server.dbus_safe(False)
    def delete_entries_for_ssid(self, ssid):
        """Delete a profile entry.

        @param ssid string of WiFi service for which to delete entries.
        @return True on success, False otherwise.

        """
        shill = self._wifi_proxy
        for profile in shill.get_profiles():
            profile_properties = shill.dbus2primitive(
                    profile.GetProperties(utf8_strings=True))
            entry_ids = profile_properties[shill.PROFILE_PROPERTY_ENTRIES]
            for entry_id in entry_ids:
                entry = profile.GetEntry(entry_id)
                if shill.dbus2primitive(entry[shill.ENTRY_FIELD_NAME]) == ssid:
                    profile.DeleteEntry(entry_id)
        return True


    def init_test_network_state(self):
        """Create a clean slate for tests with respect to remembered networks.

        For shill, this means popping and removing profiles before adding a
        'test' profile.

        @return True iff operation succeeded, False otherwise.

        """
        # TODO(wiley) We've not seen this problem before, but there could
        #             still be remembered networks in the default profile.
        #             at the very least, this profile has the ethernet
        #             entry.
        self.clean_profiles()
        self.remove_profile(self.DEFAULT_TEST_PROFILE_NAME)
        worked = self.create_profile(self.DEFAULT_TEST_PROFILE_NAME)
        if worked:
            worked = self.push_profile(self.DEFAULT_TEST_PROFILE_NAME)
        return worked


    @xmlrpc_server.dbus_safe(False)
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


    @xmlrpc_server.dbus_safe(False)
    def get_active_wifi_SSIDs(self):
        """@return list of string SSIDs with at least one BSS we've scanned."""
        return self._wifi_proxy.get_active_wifi_SSIDs()


    def enable_ui(self):
        """@return True iff the UI was successfully started."""
        return cros_ui.start(allow_fail=True) == 0


    def sync_time_to(self, epoch_seconds):
        """Sync time on the DUT to |epoch_seconds| from the epoch.

        @param epoch_seconds: float number of seconds from the epoch.

        """
        utils.run('date -u --set=@%f' % epoch_seconds)
        return True


    @staticmethod
    def do_suspend(seconds):
        """Suspend DUT using the power manager.

        @param seconds: The number of seconds to suspend the device.

        """
        return sys_power.do_suspend(seconds)


    @staticmethod
    def do_suspend_bg(seconds):
        """Suspend DUT using the power manager - non-blocking.

        @param seconds int The number of seconds to suspend the device.

        """
        process = multiprocessing.Process(target=sys_power.do_suspend,
                                          args=(seconds, 1))
        process.start()
        return True


    def clear_supplicant_blacklist(self):
        """Clear wpa_supplicant's AP blacklist.

        @return stdout and stderr returns from underlying |wpa| command.

        """
        return wifi_proxy.WifiProxy.clear_supplicant_blacklist()


    @xmlrpc_server.dbus_safe(False)
    def get_roam_threshold(self, wifi_interface):
        """Get roam threshold for a specified wifi interface.

        @param wifi_interface: string name of interface being queried.
        @return integer value of the roam threshold.

        """
        interface = {'Name': wifi_interface}
        dbus_object = self._wifi_proxy.find_object(self.DBUS_DEVICE,
                                                   interface)
        if dbus_object is None:
            return False

        object_properties = dbus_object.GetProperties(utf8_strings=True)
        if self.ROAM_THRESHOLD not in object_properties:
            return False

        return self._wifi_proxy.dbus2primitive(
                object_properties[self.ROAM_THRESHOLD])


    def request_roam(self, bssid):
        """Request that we roam to the specified BSSID.

        Note that this operation assumes that:

        1) We're connected to an SSID for which |bssid| is a member.
        2) There is a BSS with an appropriate ID in our scan results.

        This method does not check for success of either the command or
        the roaming operation.

        @param bssid: string BSSID of BSS to roam to.

        """
        utils.run('su wpa -s /usr/bin/wpa_cli roam %s' % bssid)
        return True


    @xmlrpc_server.dbus_safe(False)
    def set_roam_threshold(self, wifi_interface, value):
        """Set roam threshold for a specified wifi interface.

        @param wifi_interface: string name of interface being modified
        @param value: integer value of the roam threshold

        @return True if it worked; false, otherwise
        """
        interface = {'Name': wifi_interface}
        dbus_object = self._wifi_proxy.find_object(self.DBUS_DEVICE,
                                                   interface)
        if dbus_object is None:
            return False

        shill_proxy.ShillProxy.set_dbus_property(dbus_object,
                                                 self.ROAM_THRESHOLD,
                                                 value)
        return True


    @xmlrpc_server.dbus_safe(False)
    def set_device_enabled(self, wifi_interface, enabled):
        """Enable or disable the WiFi device.

        @param wifi_interface: string name of interface being modified.
        @param enabled: boolean; true if this device should be enabled,
                false if this device should be disabled.
        @return True if it worked; false, otherwise

        """
        interface = {'Name': wifi_interface}
        dbus_object = self._wifi_proxy.find_object(self.DBUS_DEVICE,
                                                   interface)
        if dbus_object is None:
            return False

        if enabled:
            dbus_object.Enable()
        else:
            dbus_object.Disable()
        return True


    def establish_tdls_link(self, wifi_interface, peer_mac_address):
        """Establish a TDLS link with |peer_mac_address| on |wifi_interface|.

        @param wifi_interface: string name of interface to establish a link on.
        @param peer_mac_address: string mac address of the TDLS peer device.

        @return True if it the operation was initiated; False otherwise

        """
        device_object = self._wifi_proxy.find_object(
                self.DBUS_DEVICE, {'Name': wifi_interface})
        if device_object is None:
            return False
        device_object.PerformTDLSOperation('Setup', peer_mac_address)
        return True


    @xmlrpc_server.dbus_safe(False)
    def query_tdls_link(self, wifi_interface, peer_mac_address):
        """Query the TDLS link with |peer_mac_address| on |wifi_interface|.

        @param wifi_interface: string name of interface to establish a link on.
        @param peer_mac_address: string mac address of the TDLS peer device.

        @return string indicating the current TDLS link status.

        """
        device_object = self._wifi_proxy.find_object(
                self.DBUS_DEVICE, {'Name': wifi_interface})
        if device_object is None:
            return None
        return self._wifi_proxy.dbus2primitive(
                device_object.PerformTDLSOperation('Status', peer_mac_address))


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    handler = logging.handlers.SysLogHandler(address = '/dev/log')
    formatter = logging.Formatter(
            'shill_xmlrpc_server: [%(levelname)s] %(message)s')
    handler.setFormatter(formatter)
    logging.getLogger().addHandler(handler)
    logging.debug('shill_xmlrpc_server main...')
    server = xmlrpc_server.XmlRpcServer('localhost',
                                         constants.SHILL_XMLRPC_SERVER_PORT)
    server.register_delegate(ShillXmlRpcDelegate())
    server.run()
