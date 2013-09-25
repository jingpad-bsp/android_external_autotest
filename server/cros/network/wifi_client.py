# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re
import signal

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import interface
from autotest_lib.client.common_lib.cros.network import ping_runner
from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.client.cros import constants
from autotest_lib.server import autotest
from autotest_lib.server import site_linux_system
from autotest_lib.server.cros import remote_command
from autotest_lib.server.cros import wifi_test_utils
from autotest_lib.server.cros.network import packet_capturer


class WiFiClient(object):
    """WiFiClient is a thin layer of logic over a remote DUT in wifitests."""

    XMLRPC_BRINGUP_TIMEOUT_SECONDS = 60

    IW_LINK_KEY_BEACON_INTERVAL = 'beacon int'
    IW_LINK_KEY_DTIM_PERIOD = 'dtim period'
    IW_LINK_KEY_FREQUENCY = 'freq'

    DEFAULT_PING_COUNT = 10
    COMMAND_PING = 'ping'


    @property
    def board(self):
        """@return string self reported board of this device."""
        if not self._board:
            lsb_release = self.host.run('cat /etc/lsb-release').stdout
            BOARD_PREFIX = 'CHROMEOS_RELEASE_BOARD='
            for line in lsb_release.splitlines():
                if line.startswith(BOARD_PREFIX):
                    self._board = line[len(BOARD_PREFIX):]
                    break
            else:
                raise error.TestError('Unable to detect board of test host.')

        return self._board


    @property
    def machine_id(self):
        """@return string unique to a particular board/cpu configuration."""
        if self._machine_id:
            return self._machine_id

        kernel_arch = self.host.run('uname -m').stdout.strip()
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
    def capabilities(self):
        """@return list of WiFi capabilities as parsed by LinuxSystem."""
        return self._capabilities


    @property
    def host(self):
        """@return host object representing the remote DUT."""
        return self._host


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
        return self._host


    @property
    def command_ifconfig(self):
        """@return string path to ifconfig command."""
        return self._command_ifconfig


    @property
    def command_ip(self):
        """@return string path to ip command."""
        return self._command_ip


    @property
    def command_iperf(self):
        """@return string path to iperf command."""
        return self._command_iperf


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


    def __init__(self, client_host, result_dir):
        """
        Construct a WiFiClient.

        @param client_host host object representing a remote host.
        @param result_dir string directory to store test logs/packet caps.

        """
        super(WiFiClient, self).__init__()
        self._board = None
        self._machine_id = None
        self._ping_thread = None
        self._host = client_host
        # Make sure the client library is on the device so that the proxy code
        # is there when we try to call it.
        client_at = autotest.Autotest(self.host)
        client_at.install()
        # Start up the XMLRPC proxy on the client
        self._shill_proxy = self.host.xmlrpc_connect(
                constants.SHILL_XMLRPC_SERVER_COMMAND,
                constants.SHILL_XMLRPC_SERVER_PORT,
                command_name=constants.SHILL_XMLRPC_SERVER_CLEANUP_PATTERN,
                ready_test_name=constants.SHILL_XMLRPC_SERVER_READY_METHOD,
                timeout_seconds=self.XMLRPC_BRINGUP_TIMEOUT_SECONDS)
        # Look up or hardcode command paths.
        self._command_ifconfig = 'ifconfig'
        self._command_ip = wifi_test_utils.must_be_installed(
                self.host, '/usr/local/sbin/ip')
        self._command_iperf = wifi_test_utils.must_be_installed(
                self.host, '/usr/local/bin/iperf')
        self._command_iptables = '/sbin/iptables'
        self._command_iw = 'iw'
        self._command_netdump = 'tcpdump'
        self._command_netperf = wifi_test_utils.must_be_installed(
                self.host, '/usr/local/bin/netperf')
        self._command_netserv = wifi_test_utils.must_be_installed(
                self.host, '/usr/local/sbin/netserver')
        self._command_ping6 = 'ping6'
        self._command_wpa_cli = 'wpa_cli'
        # Look up the WiFi device (and its MAC) on the client.
        devs = wifi_test_utils.get_wlan_devs(self.host, self.command_iw)
        if not devs:
            raise error.TestFail('No wlan devices found on %s.' %
                                 self.host.hostname)

        if len(devs) > 1:
            logging.warning('Warning, found multiple WiFi devices on %s: %r',
                            self.host.hostname, devs)
        self._wifi_if = devs[0]
        self._interface = interface.Interface(self._wifi_if, host=self.host)
        # Used for packet captures.
        self._packet_capturer = packet_capturer.get_packet_capturer(
                self.host, host_description='client', ignore_failures=True)
        self._result_dir = result_dir

        self._firewall_rules = []
        # Turn off powersave mode by default.
        self.powersave_switch(False)
        # It is tempting to make WiFiClient a type of LinuxSystem, but most of
        # the functionality there only makes sense for systems that want to
        # manage their own WiFi interfaces.  On client devices however, shill
        # does that work.
        system = site_linux_system.LinuxSystem(self.host, {}, 'client')
        self._capabilities = system.capabilities
        self._raise_logging_level()
        self._ping_runner = ping_runner.PingRunner(host=self.host)


    def _raise_logging_level(self):
        """Raises logging levels for WiFi on DUT."""
        self.host.run('wpa_debug excessive')
        self.host.run('ff_debug --level -5')
        self.host.run('ff_debug +wifi')


    def close(self):
        """Tear down state associated with the client."""
        if self._ping_thread is not None:
            self.ping_bg_stop()
        self.stop_capture()
        self.powersave_switch(False)
        self.shill.clean_profiles()
        # This kills the RPC server.
        logging.debug('Cleaning up host object for client')
        self._host.close()


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
        """Opens up firewall to run iperf/netperf tests.

        By default, we have a firewall rule for NFQUEUE (see crbug.com/220736).
        In order to run iperf test, we need to add a new firewall rule BEFORE
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
            self._firewall_rules.remove(rule)


    def start_capture(self):
        """Start a packet capture.

        Attempt to start a host based OTA capture.  If the driver stack does
        not support creating monitor interfaces, fall back to managed interface
        packet capture.  Only one ongoing packet capture is supported at a time.

        """
        self.stop_capture()
        devname = self._packet_capturer.create_managed_monitor(self.wifi_if)
        if devname is None:
            logging.warning('Failure creating monitor interface; doing '
                            'managed packet capture instead.')
            devname = self.wifi_if
        self._packet_capturer.start_capture(devname, self._result_dir)


    def stop_capture(self):
        """Stop a packet capture and copy over the results."""
        self._packet_capturer.stop()


    def check_iw_link_value(self, iw_link_key, desired_value):
        """Assert that the current wireless link property is |desired_value|.

        @param iw_link_key string one of IW_LINK_KEY_* defined above.
        @param desired_value string desired value of iw link property.

        """
        result = self.host.run('%s dev %s link' % (self.command_iw,
                                                   self.wifi_if))
        find_re = re.compile('\s*%s:\s*(.*\S)\s*$' % iw_link_key)
        find_results = filter(bool, map(find_re.match,
                                        result.stdout.splitlines()))
        if not find_results:
            raise error.TestFail('Could not find iw link property %s.' %
                                 iw_link_key)

        actual_value = find_results[0].group(1)
        desired_value = str(desired_value)
        if actual_value != str(desired_value):
            raise error.TestFail('Wanted iw link property %s value %s, but '
                                 'got %s instead.' % (iw_link_key,
                                                      desired_value,
                                                      actual_value))

        logging.info('Found iw link key %s with value %s.',
                     iw_link_key, actual_value)


    def powersave_switch(self, turn_on):
        """Toggle powersave mode for the DUT.

        @param turn_on bool True iff powersave mode should be turned on.

        """
        mode = 'off'
        if turn_on:
            mode = 'on'
        self.host.run('iw dev %s set power_save %s' % (self.wifi_if, mode))


    def check_powersave(self, should_be_on):
        """Check that powersave mode is on or off.

        @param should_be_on bool True iff powersave mode should be on.

        """
        result = self.host.run("iw dev %s get power_save" % self.wifi_if)
        output = result.stdout.rstrip()       # NB: chop \n
        # Output should be either "Power save: on" or "Power save: off".
        find_re = re.compile('([^:]+):\s+(\w+)')
        find_results = find_re.match(output)
        if not find_results:
            raise error.TestFail("wanted %s but not found" % want)
        actually_on = find_results.group(2) == 'on'
        if should_be_on:
            wording = 'on'
        else:
            wording = 'off'
        if should_be_on != actually_on:
            raise error.TestFail('Powersave mode should be %s, but it is not.' %
                                 wording)

        logging.debug('Power save is indeed %s.', wording)


    def scan(self, frequencies, ssids):
        """Request a scan and check that certain SSIDs appear in the results.

        @param frequencies list of int WiFi frequencies to scan for.
        @param ssids list of string ssids to probe request for.

        """
        scan_params = ''
        if frequencies:
           scan_params += ' freq %s' % ' '.join(map(str, frequencies))
        if ssids:
           scan_params += ' ssid "%s"' % '" "'.join(ssids)
        result = self.host.run('%s dev %s scan%s' % (self.command_iw,
                                                     self.wifi_if,
                                                     scan_params))
        scan_lines = result.stdout.splitlines()
        for ssid in ssids:
            if ssid and ('\tSSID: %s' % ssid) not in scan_lines:
                raise error.TestFail('SSID %s is not in scan results: %s' %
                                     (ssid, result.stdout))


    def configure_bgscan(self, configuration):
        """Control wpa_supplicant bgscan.

        @param configuration BgscanConfiguration describes a configuration.

        """
        configuration.interface = self.wifi_if
        if not self._shill_proxy.configure_bgscan(configuration):
            raise error.TestError('Background scan configuration failed.')

        logging.info('bgscan configured.')


    def disable_bgscan(self):
        """Disable wpa_supplicant bgscan."""
        params = xmlrpc_datatypes.BgscanConfiguration()
        params.interface = self.wifi_if
        params.method = xmlrpc_datatypes.BgscanConfiguration.SCAN_METHOD_NONE
        self.configure_bgscan(params)


    def enable_bgscan(self):
        """Enable wpa_supplicant bgscan."""
        klass = xmlrpc_datatypes.BgscanConfiguration
        params = xmlrpc_datatypes.BgscanConfiguration(
                interface=self.wifi_if,
                method=klass.SCAN_METHOD_DEFAULT,
                short_interval=klass.DEFAULT_SHORT_INTERVAL_SECONDS,
                long_interval=klass.DEFAULT_LONG_INTERVAL_SECONDS)
        self.configure_bgscan(params)


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
