# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re
import signal
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import interface
from autotest_lib.client.common_lib.cros.network import ping_runner
from autotest_lib.client.cros import constants
from autotest_lib.server import autotest
from autotest_lib.server import site_linux_system
from autotest_lib.server.cros import remote_command
from autotest_lib.server.cros import wifi_test_utils
from autotest_lib.server.cros.network import wpa_cli_proxy
from autotest_lib.server.hosts import adb_host


class WiFiClient(site_linux_system.LinuxSystem):
    """WiFiClient is a thin layer of logic over a remote DUT in wifitests."""

    XMLRPC_BRINGUP_TIMEOUT_SECONDS = 60

    DEFAULT_PING_COUNT = 10
    COMMAND_PING = 'ping'

    MAX_SERVICE_GONE_TIMEOUT_SECONDS = 60

    # List of interface names we won't consider for use as "the" WiFi interface
    # on Android hosts.
    WIFI_IF_BLACKLIST = ['p2p0']

    UNKNOWN_BOARD_TYPE = 'unknown'


    @property
    def board(self):
        """@return string self reported board of this device."""
        if self._board is None:
            # Remove 'board:' prefix.
            self._board = self.host.get_board().split(':')[1]
        return self._board


    @property
    def machine_id(self):
        """@return string unique to a particular board/cpu configuration."""
        if self._machine_id:
            return self._machine_id

        uname_result = self.host.run('uname -m', ignore_status=True)
        kernel_arch = ''
        if not uname_result.exit_status and uname_result.stdout.find(' ') < 0:
            kernel_arch = uname_result.stdout.strip()
        cpu_info = self.host.run('cat /proc/cpuinfo').stdout.splitlines()
        cpu_count = len(filter(lambda x: x.lower().startswith('bogomips'),
                               cpu_info))
        cpu_count_str = ''
        if cpu_count:
            cpu_count_str = 'x%d' % cpu_count
        ghz_value = ''
        ghz_pattern = re.compile('([0-9.]+GHz)')
        for line in cpu_info:
            match = ghz_pattern.search(line)
            if match is not None:
                ghz_value = '_' + match.group(1)
                break

        return '%s_%s%s%s' % (self.board, kernel_arch, ghz_value, cpu_count_str)


    @property
    def powersave_on(self):
        """@return bool True iff WiFi powersave mode is enabled."""
        result = self.host.run("iw dev %s get power_save" % self.wifi_if)
        output = result.stdout.rstrip()       # NB: chop \n
        # Output should be either "Power save: on" or "Power save: off".
        find_re = re.compile('([^:]+):\s+(\w+)')
        find_results = find_re.match(output)
        if not find_results:
            raise error.TestFail('Failed to find power_save parameter '
                                 'in iw results.')

        return find_results.group(2) == 'on'


    @property
    def shill(self):
        """@return shill RPCProxy object."""
        return self._shill_proxy


    @property
    def client(self):
        """Deprecated accessor for the client host.

        The term client is used very loosely in old autotests and this
        accessor should not be used in new code.  Use host() instead.

        @return host object representing a remote DUT.

        """
        return self.host


    @property
    def command_ip(self):
        """@return string path to ip command."""
        return self._command_ip


    @property
    def command_iptables(self):
        """@return string path to iptables command."""
        return self._command_iptables


    @property
    def command_iw(self):
        """@return string path to iw command."""
        return self._command_iw


    @property
    def command_netperf(self):
        """@return string path to netperf command."""
        return self._command_netperf


    @property
    def command_netserv(self):
        """@return string path to netserv command."""
        return self._command_netserv


    @property
    def command_ping6(self):
        """@return string path to ping6 command."""
        return self._command_ping6


    @property
    def command_wpa_cli(self):
        """@return string path to wpa_cli command."""
        return self._command_wpa_cli


    @property
    def wifi_if(self):
        """@return string wifi device on machine (e.g. mlan0)."""
        return self._wifi_if


    @property
    def wifi_mac(self):
        """@return string MAC address of self.wifi_if."""
        return self._interface.mac_address


    @property
    def wifi_ip(self):
        """@return string IPv4 address of self.wifi_if."""
        return self._interface.ipv4_address


    @property
    def wifi_signal_level(self):
        """Returns the signal level of this DUT's WiFi interface.

        @return int signal level of connected WiFi interface or None (e.g. -67).

        """
        return self._interface.signal_level


    def wifi_noise_level(self, frequency_mhz):
        """Returns the noise level of this DUT's WiFi interface.

        @param frequency_mhz: frequency at which the noise level should be
               measured and reported.
        @return int signal level of connected WiFi interface in dBm (e.g. -67)
                or None if the value is unavailable.

        """
        return self._interface.noise_level(frequency_mhz)


    def __init__(self, client_host, result_dir):
        """
        Construct a WiFiClient.

        @param client_host host object representing a remote host.
        @param result_dir string directory to store test logs/packet caps.

        """
        super(WiFiClient, self).__init__(client_host, 'client',
                                         inherit_interfaces=True)
        self._board = None
        self._command_ip = 'ip'
        self._command_iptables = 'iptables'
        self._command_iw = 'iw'
        self._command_netperf = 'netperf'
        self._command_netserv = 'netserver'
        self._command_ping6 = 'ping6'
        self._command_wpa_cli = 'wpa_cli'
        self._machine_id = None
        self._ping_runner = ping_runner.PingRunner(host=self.host)
        self._ping_thread = None
        self._result_dir = result_dir
        if isinstance(self.host, adb_host.ADBHost):
            # Look up the WiFi device (and its MAC) on the client.
            devs = self.iw_runner.list_interfaces(desired_if_type='managed')
            devs = [dev for dev in devs
                    if dev.if_name not in self.WIFI_IF_BLACKLIST]
            if not devs:
                raise error.TestFail('No wlan devices found on %s.' %
                                     self.host.hostname)

            if len(devs) > 1:
                logging.warning('Warning, found multiple WiFi devices on '
                                '%s: %r', self.host.hostname, devs)
            self._wifi_if = devs[0].if_name
            self._shill_proxy = wpa_cli_proxy.WpaCliProxy(
                    self.host, self._wifi_if)
        else:
            # Make sure the client library is on the device so that the proxy
            # code is there when we try to call it.
            client_at = autotest.Autotest(self.host)
            client_at.install()
            # Start up the XMLRPC proxy on the client
            self._shill_proxy = self.host.xmlrpc_connect(
                    constants.SHILL_XMLRPC_SERVER_COMMAND,
                    constants.SHILL_XMLRPC_SERVER_PORT,
                    command_name=constants.SHILL_XMLRPC_SERVER_CLEANUP_PATTERN,
                    ready_test_name=constants.SHILL_XMLRPC_SERVER_READY_METHOD,
                    timeout_seconds=self.XMLRPC_BRINGUP_TIMEOUT_SECONDS)
            interfaces = self._shill_proxy.list_controlled_wifi_interfaces()
            if not interfaces:
                logging.debug('No interfaces managed by shill. Rebooting host')
                self.host.reboot()
                raise error.TestError('No interfaces managed by shill on %s' %
                                      self.host.hostname)
            self._wifi_if = interfaces[0]
            self._raise_logging_level()
        self._interface = interface.Interface(self._wifi_if, host=self.host)
        self._firewall_rules = []
        # Turn off powersave mode by default.
        self.powersave_switch(False)
        # All tests that use this object assume the interface starts enabled.
        self.set_device_enabled(self._wifi_if, True)


    def _assert_method_supported(self, method_name):
        """Raise a TestNAError if the XMLRPC proxy has no method |method_name|.

        @param method_name: string name of method that should exist on the
                XMLRPC proxy.

        """
        if not self._supports_method(method_name):
            raise error.TestNAError('%s() is not supported' % method_name)


    def _raise_logging_level(self):
        """Raises logging levels for WiFi on DUT."""
        self.host.run('wpa_debug excessive')
        self.host.run('ff_debug --level -5')
        self.host.run('ff_debug +wifi')


    def _supports_method(self, method_name):
        """Checks if |method_name| is supported on the remote XMLRPC proxy.

        autotest will, for their own reasons, install python files in the
        autotest client package that correspond the version of the build
        rather than the version running on the autotest drone.  This
        creates situations where we call methods on the client XMLRPC proxy
        that don't exist in that version of the code.  This detects those
        situations so that we can degrade more or less gracefully.

        @param method_name: string name of method that should exist on the
                XMLRPC proxy.
        @return True if method is available, False otherwise.

        """
        # Make no assertions about ADBHost support.  We don't use an XMLRPC
        # proxy with those hosts anyway.
        supported = (isinstance(self.host, adb_host.ADBHost) or
                     method_name in self._shill_proxy.system.listMethods())
        if not supported:
            logging.warning('%s() is not supported on older images',
                            method_name)
        return supported


    def close(self):
        """Tear down state associated with the client."""
        if self._ping_thread is not None:
            self.ping_bg_stop()
        self.stop_capture()
        self.powersave_switch(False)
        self.shill.clean_profiles()
        super(WiFiClient, self).close()


    def ping(self, ping_config):
        """Ping an address from the client and return the command output.

        @param ping_config parameters for the ping command.
        @return a PingResult object.

        """
        logging.info('Pinging from the client.')
        return self._ping_runner.ping(ping_config)


    def ping_bg(self, ping_ip, ping_args):
        """Ping an address from the client in the background.

        Only one instance of a background ping is supported at a time.

        @param ping_ip string IPv4 address for the client to ping.
        @param ping_args dict of parameters understood by
                wifi_test_utils.ping_args().

        """
        if self._ping_thread is not None:
            raise error.TestFail('Tried to start a background ping without '
                                 'stopping an earlier ping.')
        cmd = '%s %s %s' % (self.COMMAND_PING,
                            wifi_test_utils.ping_args(ping_args),
                            ping_ip)
        self._ping_thread = remote_command.Command(
                self.host, cmd, pkill_argument=self.COMMAND_PING)


    def ping_bg_stop(self):
        """Stop pinging an address from the client in the background.

        Clean up state from a previous call to ping_bg.  If requested,
        statistics from the background ping run may be saved.

        """
        if self._ping_thread is None:
            logging.info('Tried to stop a bg ping, but none was started')
            return
        # Sending SIGINT gives us stats at the end, how nice.
        self._ping_thread.join(signal.SIGINT)
        self._ping_thread = None


    def firewall_open(self, proto, src):
        """Opens up firewall to run netperf tests.

        By default, we have a firewall rule for NFQUEUE (see crbug.com/220736).
        In order to run netperf test, we need to add a new firewall rule BEFORE
        this NFQUEUE rule in the INPUT chain.

        @param proto a string, test traffic protocol, e.g. udp, tcp.
        @param src a string, subnet/mask.

        @return a string firewall rule added.

        """
        rule = 'INPUT -s %s/32 -p %s -m %s -j ACCEPT' % (src, proto, proto)
        self.host.run('%s -I %s' % (self._command_iptables, rule))
        self._firewall_rules.append(rule)
        return rule


    def firewall_cleanup(self):
        """Cleans up firewall rules."""
        for rule in self._firewall_rules:
            self.host.run('%s -D %s' % (self._command_iptables, rule))
        self._firewall_rules = []


    def sync_host_times(self):
        """Set time on our DUT to match local time."""
        epoch_seconds = time.time()
        self.shill.sync_time_to(epoch_seconds)


    def check_iw_link_value(self, iw_link_key, desired_value):
        """Assert that the current wireless link property is |desired_value|.

        @param iw_link_key string one of IW_LINK_KEY_* defined in iw_runner.
        @param desired_value string desired value of iw link property.

        """
        actual_value = self.get_iw_link_value(iw_link_key)
        desired_value = str(desired_value)
        if actual_value != desired_value:
            raise error.TestFail('Wanted iw link property %s value %s, but '
                                 'got %s instead.' % (iw_link_key,
                                                      desired_value,
                                                      actual_value))


    def get_iw_link_value(self, iw_link_key, ignore_failures=False):
        return self.iw_runner.get_link_value(self.wifi_if, iw_link_key,
                                             ignore_failures=ignore_failures)


    def powersave_switch(self, turn_on):
        """Toggle powersave mode for the DUT.

        @param turn_on bool True iff powersave mode should be turned on.

        """
        mode = 'off'
        if turn_on:
            mode = 'on'
        self.host.run('iw dev %s set power_save %s' % (self.wifi_if, mode))


    def timed_scan(self, frequencies, ssids, scan_timeout_seconds=10,
                   retry_timeout_seconds=10):
        """Request timed scan to discover given SSIDs.

        This method will retry for a default of |retry_timeout_seconds| until it
        is able to successfully kick off a scan.  Sometimes, the device on the
        DUT claims to be busy and rejects our requests. It will raise error
        if the scan did not complete within |scan_timeout_seconds| or it was
        not able to discover the given SSIDs.

        @param frequencies list of int WiFi frequencies to scan for.
        @param ssids list of string ssids to probe request for.
        @param scan_timeout_seconds: float number of seconds the scan
                operation not to exceed.
        @param retry_timeout_seconds: float number of seconds to retry scanning
                if the interface is busy.  This does not retry if certain
                SSIDs are missing from the results.

        """
        start_time = time.time()
        while time.time() - start_time < retry_timeout_seconds:
            scan_result = self.iw_runner.timed_scan(
                    self.wifi_if, frequencies=frequencies, ssids=ssids)

            if scan_result is not None:
                break

            time.sleep(0.5)
        else:
            raise error.TestFail('Unable to trigger scan on client.')

        # Verify scan operation completed within given timeout
        if scan_result.time > scan_timeout_seconds:
            raise error.TestFail('Scan time %.2fs exceeds the scan timeout' %
                                 (scan_result.time))

        # Verify all ssids are discovered
        for ssid in ssids:
            if not ssid:
                continue

            for bss in scan_result.bss_list:
                if bss.ssid == ssid:
                    break
            else:
                raise error.TestFail('SSID %s is not in scan results: %r' %
                                     (ssid, scan_result.bss_list))

        logging.info('Wifi scan completed in %.2f seconds', scan_result.time)


    def scan(self, frequencies, ssids, timeout_seconds=10):
        """Request a scan and check that certain SSIDs appear in the results.

        This method will retry for a default of |timeout_seconds| until it is
        able to successfully kick off a scan.  Sometimes, the device on the DUT
        claims to be busy and rejects our requests.

        @param frequencies list of int WiFi frequencies to scan for.
        @param ssids list of string ssids to probe request for.
        @param timeout_seconds: float number of seconds to retry scanning
                if the interface is busy.  This does not retry if certain
                SSIDs are missing from the results.

        """
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            bss_list = self.iw_runner.scan(
                    self.wifi_if, frequencies=frequencies, ssids=ssids)
            if bss_list is not None:
                break

            time.sleep(0.5)
        else:
            raise error.TestFail('Unable to trigger scan on client.')

        for ssid in ssids:
            if not ssid:
                continue

            for bss in bss_list:
                if bss.ssid == ssid:
                    break

            else:
                raise error.TestFail('SSID %s is not in scan results: %r' %
                                     (ssid, bss_list))


    def wait_for_service_states(self, ssid, states, timeout_seconds):
        """Waits for a WiFi service to achieve one of |states|.

        @param ssid string name of network being queried
        @param states tuple list of states for which the caller is waiting
        @param timeout_seconds int seconds to wait for a state in |states|

        """
        logging.info('Waiting for %s to reach one of %r...', ssid, states)
        success, state, time  = self._shill_proxy.wait_for_service_states(
                ssid, states, timeout_seconds)
        logging.info('...ended up in state \'%s\' (%s) after %f seconds.',
                     state, 'success' if success else 'failure', time)
        return success, state, time


    def do_suspend(self, seconds):
        """Puts the DUT in suspend power state for |seconds| seconds.

        @param seconds: The number of seconds to suspend the device.

        """
        logging.info('Suspending DUT for %d seconds...', seconds)
        self._shill_proxy.do_suspend(seconds)
        logging.info('...done suspending')


    def do_suspend_bg(self, seconds):
        """Suspend DUT using the power manager - non-blocking.

        @param seconds: The number of seconds to suspend the device.

        """
        logging.info('Suspending DUT (in background) for %d seconds...',
                     seconds)
        self._shill_proxy.do_suspend_bg(seconds)


    def clear_supplicant_blacklist(self):
        """Clear's the AP blacklist on the DUT.

        @return stdout and stderror returns passed from
                self._shill_proxy.clear_supplicant_blacklist()

        """
        stdoutdata, stderrdata = self._shill_proxy.clear_supplicant_blacklist()
        logging.info('wpa_cli blacklist clear: out:%r err:%r', stdoutdata,
                     stderrdata)
        return stdoutdata, stderrdata


    def get_active_wifi_SSIDs(self):
        """Get a list of visible SSID's around the DUT

        @return list of string SSIDs

        """
        self._assert_method_supported('get_active_wifi_SSIDs')
        return self._shill_proxy.get_active_wifi_SSIDs()


    def get_roam_threshold(self, wifi_interace):
        """Get wpa_supplicant's roaming theshold for the specified interface.

        @param wifi_interface: string name of the wifi_interface.
        @return integer roam threshold or False if something went wrong.

        """
        return self._shill_proxy.get_roam_threshold(wifi_interace)


    def set_roam_threshold(self, wifi_interace, value):
        """Set wpa_supplicant's roaming theshold for the specified interface.

        @param wifi_interace: string name of the wifi_interface.
        @param value: integer to which to set the roam_threshold
        @return True if it worked; False, otherwise

        """
        return self._shill_proxy.set_roam_threshold(wifi_interace, value)


    def set_device_enabled(self, wifi_interace, value,
                           fail_on_unsupported=False):
        """Enable or disable the WiFi device.

        @param wifi_interface: string name of interface being modified.
        @param enabled: boolean; true if this device should be enabled,
                false if this device should be disabled.
        @return True if it worked; False, otherwise.

        """
        if fail_on_unsupported:
            self._assert_method_supported('set_device_enabled')
        elif not self._supports_method('set_device_enabled'):
            return False
        return self._shill_proxy.set_device_enabled(wifi_interace, value)


    def add_arp_entry(self, ip_address, mac_address):
        """Add an ARP entry to the table associated with the WiFi interface.

        @param ip_address: string IP address associated with the new ARP entry.
        @param mac_address: string MAC address associated with the new ARP
                entry.

        """
        self.host.run('ip neigh add %s lladdr %s dev %s nud perm' %
                      (ip_address, mac_address, self.wifi_if))


    def establish_tdls_link(self, mac_address):
        """Establish a TDLS link with |mac_address|.

        @param mac_address: string MAC address associated with the TDLS peer.

        @return bool True if operation initiated successfully, False otherwise.

        """
        return self._shill_proxy.establish_tdls_link(self.wifi_if, mac_address)


    def query_tdls_link(self, mac_address):
        """Query a TDLS link with |mac_address|.

        @param mac_address: string MAC address associated with the TDLS peer.

        @return string indicating current TDLS connectivity.

        """
        return self._shill_proxy.query_tdls_link(self.wifi_if, mac_address)


    def request_roam(self, bssid):
        """Request that we roam to the specified BSSID.

        Note that this operation assumes that:

        1) We're connected to an SSID for which |bssid| is a member.
        2) There is a BSS with an appropriate ID in our scan results.

        This method does not check for success of either the command or
        the roaming operation.

        @param bssid: string MAC address of bss to roam to.

        """
        self._assert_method_supported('request_roam')
        self._shill_proxy.request_roam(bssid)


    def wait_for_ssid_vanish(self, ssid):
        """Wait for shill to notice that there are no BSS's for an SSID present.

        Raise a test failing exception if this does not come to pass.

        @param ssid: string SSID of the network to require be missing.

        """
        start_time = time.time()
        while time.time() - start_time < self.MAX_SERVICE_GONE_TIMEOUT_SECONDS:
            visible_ssids = self.get_active_wifi_SSIDs()
            logging.info('Got service list: %r', visible_ssids)
            if ssid not in visible_ssids:
                return

            self.scan(frequencies=[], ssids=[], timeout_seconds=30)
        else:
            raise error.TestFail('shill should mark the BSS as not present')


    def reassociate(self, timeout_seconds=10):
        """Reassociate to the connected network.

        @param timeout_seconds: float number of seconds to wait for operation
                to complete.

        """
        logging.info('Attempt to reassociate')
        with self.iw_runner.get_event_logger() as logger:
            logger.start()
            # Issue reassociate command to wpa_supplicant
            result = self.host.run('su wpa -s /usr/bin/wpa_cli reassociate')
            if not result.stdout.strip().endswith('OK'):
                raise error.TestFail('wpa_cli reassociate command failed')

            # Wait for the timeout seconds for association to complete
            time.sleep(timeout_seconds)

            # Stop iw event logger
            logger.stop()

            # Get association time based on the iw event log
            reassociate_time = logger.get_association_time()
            if reassociate_time is None or reassociate_time > timeout_seconds:
                raise error.TestFail(
                        'Failed to reassociate within given timeout')
            logging.info('Reassociate time: %.2f seconds', reassociate_time)
