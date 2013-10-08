# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import logging
import re
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.server import site_linux_router


# Used to represent stations we parse out of scan results.
Station = collections.namedtuple('Station',
                                 ['bssid', 'frequency', 'signal', 'ssid'])

class WpaCliProxy(object):
    """Interacts with a DUT through wpa_cli rather than shill."""

    SCANNING_INTERVAL_SECONDS = 5
    POLLING_INTERVAL_SECONDS = 0.5


    def __init__(self, host, wifi_if):
        self._host = host
        self._created_networks = {}
        # TODO(wiley) Hardcoding this IFNAME prefix makes some big assumptions.
        #             we'll need to discover this parameter as it becomes more
        #             generally useful.
        self._wpa_cli_cmd = 'wpa_cli IFNAME=%s' % wifi_if


    def _add_network(self, ssid):
        """
        Add a wpa_supplicant network for ssid.

        @param ssid string: name of network to add.
        @return int network id of added network.

        """
        add_result = self._run_wpa_cli_cmd('add_network', check_result=False)
        network_id = int(add_result.stdout.splitlines()[-1])
        self._run_wpa_cli_cmd('set_network %d ssid \'\\"%s\\"\'' %
                              (network_id, ssid))
        self._created_networks[ssid] = network_id
        logging.debug('Added network %s=%d', ssid, network_id)
        return network_id


    def _run_wpa_cli_cmd(self, command, check_result=True):
        """
        Run a wpa_cli command and optionally check the result.

        @param command string: suffix of a command to be prefixed with
                an appropriate wpa_cli for this host.
        @param check_result bool: True iff we want to check that the
                command comes back with an 'OK' response.
        @return result object returned by host.run.

        """
        result = self._host.run('%s %s' % (self._wpa_cli_cmd, command))
        if check_result and not result.stdout.strip().endswith('OK'):
            raise error.TestFail('wpa_cli command failed: %s' % command)

        return result


    def _wait_status(self, ssid, field_name, value_check, timeout_seconds):
        """
        Wait for `wpa_cli status` to have a field with a certain value.

        @param ssid string: ssid of the network we expect that status to match.
        @param field_name string: name of field to look for (e.g. ip_address).
        @param value_check function: function that takes the string value of the
                specified field and returns True if it is the value we're
                waiting to see.
        @param timeout_seconds numeric: number of seconds to wait.
        @return a tuple (success, duration_seconds) where success is a boolean
                and duration is a float.

        """
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            duration = time.time() - start_time
            status_result = self._run_wpa_cli_cmd('status', check_result=False)
            status_pairs = dict([line.strip().split('=', 1)
                                 for line in status_result.stdout.splitlines()
                                 if line.find('=') > 0])
            if (status_pairs.get('ssid', None) == ssid and
                    value_check(status_pairs.get(field_name, None))):
                return (True, duration)

            time.sleep(self.POLLING_INTERVAL_SECONDS)
        duration = time.time() - start_time
        return (False, duration)


    def clean_profiles(self):
        """Remove state associated with past networks we've connected to."""
        # list_networks output looks like:
        # Using interface 'wlan0'^M
        # network id / ssid / bssid / flags^M
        # 0    SimpleConnect_jstja_ch1 any     [DISABLED]^M
        # 1    SimpleConnect_gjji2_ch6 any     [DISABLED]^M
        # 2    SimpleConnect_xe9d1_ch11        any     [DISABLED]^M
        list_networks_result = self._run_wpa_cli_cmd(
                'list_networks', check_result=False)
        start_parsing = False
        for line in list_networks_result.stdout.splitlines():
            if not start_parsing:
                if line.startswith('network id'):
                    start_parsing = True
                continue

            network_id = int(line.split()[0])
            self._run_wpa_cli_cmd('remove_network %d' % network_id)
        self._created_networks = {}


    def create_profile(self, _):
        """
        This is a no op, since we don't have profiles.

        @param _ ignored.

        """
        logging.info('Skipping create_profile on %s', self.__class__.__name__)


    def pop_profile(self, _):
        """
        This is a no op, since we don't have profiles.

        @param _ ignored.

        """
        logging.info('Skipping pop_profile on %s', self.__class__.__name__)


    def push_profile(self, _):
        """
        This is a no op, since we don't have profiles.

        @param _ ignored.

        """
        logging.info('Skipping push_profile on %s', self.__class__.__name__)


    def remove_profile(self, _):
        """
        This is a no op, since we don't have profiles.

        @param _ ignored.

        """
        logging.info('Skipping remove_profile on %s', self.__class__.__name__)


    def init_test_network_state(self):
        """Create a clean slate for tests with respect to remembered networks.

        For wpa_cli hosts, this means removing all remembered networks.

        @return True iff operation succeeded, False otherwise.

        """
        self.clean_profiles()
        return True


    def connect_wifi(self, assoc_params):
        """
        Connect to the WiFi network described by AssociationParameters.

        @param assoc_params AssociationParameters object.
        @return serialized AssociationResult object.

        """
        logging.debug('connect_wifi()')
        # Ouptut should look like:
        #   Using interface 'wlan0'
        #   0
        assoc_result = xmlrpc_datatypes.AssociationResult()
        network_id = self._add_network(assoc_params.ssid)
        if assoc_params.is_hidden:
            self._run_wpa_cli_cmd('set_network %d %s %s' %
                                  (network_id, 'scan_ssid', '1'))

        sec_config = assoc_params.security_config
        for field, value in sec_config.get_wpa_cli_properties().iteritems():
            self._run_wpa_cli_cmd('set_network %d %s %s' %
                                  (network_id, field, value))
        self._run_wpa_cli_cmd('select_network %d' % network_id)

        # Wait for an appropriate BSS to appear in scan results.
        scan_results_pattern = '\t'.join(['([0-9a-f:]{17})', # BSSID
                                          '([0-9]+)',  # Frequency
                                          '(-[0-9]+)',  # Signal level
                                          '(.*)',  # Encryption types
                                          '(.*)'])  # SSID
        last_scan_time = -1.0
        start_time = time.time()
        while time.time() - start_time < assoc_params.discovery_timeout:
            assoc_result.discovery_time = time.time() - start_time
            scan_result = self._run_wpa_cli_cmd('scan_results',
                                                check_result=False)
            found_stations = []
            for line in scan_result.stdout.strip().splitlines():
                match = re.match(scan_results_pattern, line)
                if match is None:
                    continue
                found_stations.append(
                        Station(bssid=match.group(1), frequency=match.group(2),
                                signal=match.group(3), ssid=match.group(5)))
            logging.debug('Found stations: %r',
                          [station.ssid for station in found_stations])
            if [station for station in found_stations
                    if station.ssid == assoc_params.ssid]:
                break

            if time.time() - last_scan_time > self.SCANNING_INTERVAL_SECONDS:
                # Sometimes this might fail with a FAIL-BUSY if the previous
                # scan hasn't finished.
                scan_result = self._run_wpa_cli_cmd('scan', check_result=False)
                if scan_result.stdout.strip().endswith('OK'):
                    last_scan_time = time.time()
            time.sleep(self.POLLING_INTERVAL_SECONDS)
        else:
            assoc_result.failure_reason = 'Discovery timed out'
            return assoc_result.serialize()

        # Wait on association to finish.
        success, assoc_result.association_time = self._wait_status(
                assoc_params.ssid,
                'wpa_state',
                lambda wpa_state: wpa_state and wpa_state == 'COMPLETED',
                assoc_params.association_timeout)
        if not success:
            assoc_result.failure_reason = 'Association timed out'
            return assoc_result.serialize()

        # Then wait for ip configuration to finish.
        ip_prefix_str = '.'.join(map(
                str,
                site_linux_router.LinuxRouter.SUBNET_PREFIX_OCTETS))
        success, assoc_result.configuration_time = self._wait_status(
                assoc_params.ssid,
                'ip_address',
                lambda real_ip: real_ip and real_ip.startswith(ip_prefix_str),
                assoc_params.configuration_timeout)
        if not success:
            assoc_result.failure_reason = 'DHCP negotiation timed out'
            return assoc_result.serialize()

        assoc_result.success = True
        logging.info('Connected to %s', assoc_params.ssid)
        return assoc_result.serialize()


    def disconnect(self, ssid):
        """
        Disconnect from a WiFi network named |ssid|.

        @param ssid string: name of network to disable in wpa_supplicant.

        """
        logging.debug('disconnect()')
        if ssid not in self._created_networks:
            return False
        self._run_wpa_cli_cmd('disable_network %d' %
                              self._created_networks[ssid])
        return True


    def sync_time_to(self, epoch_seconds):
        """
        Sync time on the DUT to |epoch_seconds| from the epoch.

        @param epoch_seconds float: number of seconds since the epoch.

        """
        # This will claim to fail, but will work anyway.
        self._host.run('date -u %f' % epoch_seconds, ignore_status=True)
