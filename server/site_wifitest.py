# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import common
import datetime
import fnmatch
import logging
import os
import re
import signal
import stat
import tempfile
import time
import traceback

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.server import autotest
from autotest_lib.server import hosts
from autotest_lib.server import site_attenuator
from autotest_lib.server import site_bsd_router
from autotest_lib.server import site_cisco_router
from autotest_lib.server import site_eap_certs
from autotest_lib.server import site_host_attributes
from autotest_lib.server import site_host_route
from autotest_lib.server import site_linux_bridge_router
from autotest_lib.server import site_linux_cros_router
from autotest_lib.server import site_linux_router
from autotest_lib.server import site_linux_server
from autotest_lib.server import site_linux_system
from autotest_lib.server import site_linux_vm_router
from autotest_lib.server import test
from autotest_lib.server.cros import remote_command
from autotest_lib.server.cros import wifi_test_utils

class ScriptNotFound(Exception):
    """Raised when site_wlan scripts cannot be found."""
    def __init__(self, scriptname):
        super(ScriptNotFound, self).__init__(
            'Script %s not found in search path' % scriptname)


class WiFiTest(object):
    """
    WiFi Test.

    Each test is specified as a dict.  There must be a "name" entry that
    gives the test name (a string) and a "steps" entry that has an ordered
    tuple of test steps, where each step is a tuple [func, {args}].

    Step funcs are one of:
      config                  configure the router/AP using the specified params
                              (ssid automatically supplied); params are give as
                              BSD ifconfig(8) parameters and translated to match
                              the target router/AP's cli syntax
      deconfig                de-configure/shut-off the router/AP
      connect                 connect client to AP using specified parameters
                              (ssid automatically supplied)
      disconnect              disconnect client from AP
      client_check_*          check the client's connection state to verify
                              a parameter was setup as expected; e.g.
                              client_check_bintval checks the beacon interval
                              set on the AP was adopted by the client
      client_monitor_start    start monitoring for wireless system events as
                              needed (e.g, kick off a process that listens)
      client_monitor_stop     stop monitoring for wireless system events
      client_check_event_*    check the client's event log for an event;
                              should always be preceded by client_monitor_start
      sleep                   pause on the autotest server for a time
      client_ping             ping the server on the client machine
      server_ping             ping the client on the server machine
      client_iperf            run iperf on the client to the server
      server_iperf            run iperf on the server to the client
      client_netperf          run netperf on the client to the server
      server_netperf          run netperf on the server to the client
      vpn_client_load_tunnel  load 'tun' device for VPN client
      vpn_client_kill         Kill the running VPN client.  Do nothing
                              if not running.
      vpn_client_connect      launch a VPN client to connect with the
                              VPN server
      client_reboot           reboots the client and waits for it to come back.
                              The amount of time to wait can be specified by a
                              'timeout' parameter, in seconds.

    Steps that are done on the client or server machine are implemented in
    this class.  Steps that are done on the wifi router are implemented in
    a separate class that knows how to control the router.  There are presently
    two classes: BSDRouter for routers based on FreeBSD and LinuxRouter for
    those based on Linux/mac80211.  Additional router support can be added
    by adding a new class and auto-selecting it in __init__.

    The WiFiTest class could be generalized to handle clients other than
    ChromeOS; this would useful for systems that use Network Manager or
    wpa_supplicant directly.
    """

    _result_expect_failure = 1
    _result_expect_success = 2
    _result_dont_care = 3

    _capability_5ghz = "5ghz"
    _capability_multi_ap = "multi_ap"
    _capability_multi_ap_same_band = "multi_ap_same_band"


    def __init__(self, name, steps, client_requirements, config):
        self.name = name
        self.steps = steps
        step_req_client, step_req_router = self.__get_step_requirements()
        self.client_requirements = (client_requirements + step_req_client)
        self.router_requirements = step_req_router
        self.perf_keyvals = {}

        self.cur_frequency   = None
        self.cur_phymode     = None
        self.cur_security    = None
        self.cur_attenuation = None
        self.vpn_kind        = None
        #
        # There is a case that leaves some profiles in profile storage but
        # not on the stack. This will cause the failure for 'profile_create'
        # in later test cases. We use a list to record the created profiles
        # and remove them all after the test case ends.
        #
        # Example:
        # 1. profile_create: top  (in profile storage)
        # 2. profile_push: top    (in profile storage and also on the stack)
        # 3. connect
        # 4. profile_pop: top     (still in profile storage)
        # 5. The test case ends with a failure.
        # 6. Another test case starts.
        # 7. profile_create: top  (failure)
        #
        self.created_profiles = []

        router = config['router']
        #
        # The server machine may be multi-homed or only on the wifi
        # network.  When only on the wifi net we suppress server_*
        # requests since we cannot initiate them from the control machine.
        #
        server = config['server']
        # NB: server may not be reachable on the control network

        self.router = None
        if not router['addr'].startswith('cisco'):
            self.router = hosts.SSHHost(router['addr'],
                                        port=int(router.get('port',22)))
        self.defssid = wifi_test_utils.get_default_ssid(self.name,
                                                        router['addr'],
                                                        self.router)

        defaults = config.get('defaults', {})
        self.deftimeout = defaults.get('timeout', 30)
        self.defpingcount = defaults.get('pingcount', 10)
        self.defwaittime = defaults.get('netperf_wait_time', 3)
        self.defiperfport = str(defaults.get('iperf_port', 12866))
        self.defnetperfport = str(defaults.get('netperf_port', 12865))
        if 'type' not in router:
            # auto-detect router type
            if router['addr'].startswith('cisco:'):
                router['addr'] = router['addr'][6:]
                router['type'] = 'cisco'
            elif site_linux_router.isLinuxRouter(self.router):
                router['type'] = 'linux'
            elif site_bsd_router.isBSDRouter(self.router):
                router['type'] = 'bsd'
            else:
                 raise error.TestFail('Unable to autodetect router type')
        if router['type'] == 'linux':
            if config['router']['addr'] == config['client']['addr']:
                self.wifi = site_linux_vm_router.LinuxVMRouter(
                    self.router, router, self.defssid)
            elif site_linux_cros_router.isLinuxCrosRouter(self.router):
                self.wifi = site_linux_cros_router.LinuxCrosRouter(
                    self.router, router, self.defssid)
            else:
                self.wifi = site_linux_bridge_router.LinuxBridgeRouter(
                    self.router, router, self.defssid)
        elif router['type'] == 'bsd':
            self.wifi = site_bsd_router.BSDRouter(self.router, router,
                self.defssid)
        elif router['type'] == 'cisco':
            self.wifi = site_cisco_router.CiscoRouter(server['addr'], router,
                self.defssid, router['addr'])
            self.router = self.wifi.get_proxy()
        else:
            raise error.TestFail('Unsupported router')

        attenuator = config.get('attenuator', dict())
        # NB: Attenuator must be reachable on the control network
        if attenuator.get('addr', None):
            attenuator_host = hosts.SSHHost(attenuator['addr'],
                                            port=int(attenuator.get('port',22)))
            self.attenuator = site_attenuator.Attenuator(attenuator_host)

        #
        # The client machine must be reachable from the control machine.
        # The address on the wifi network is retrieved each time it
        # associates to the router.
        #
        client = config['client']
        self.client = hosts.create_host(client['addr'])
        self.client_at = autotest.Autotest(self.client)
        self.client_wifi_ip = None            # client's IP address on wifi net
        self.client_wifi_device_path = None   # client's flimflam wifi path
        self.client_signal_info = {}
        self.client_installed_scripts = {}
        self.client_logfile = client.get("logfile", "/var/log/messages")
        self.ping_stats = {}

        if not 'addr' in server:
            raise error.TestError('All current WiFi tests require a server '
                                  'reachable on the control network.')

        # The 'hosting_server' is a machine which hosts network
        # services, such as OpenVPN or StrongSwan.
        self.hosting_server = site_linux_server.LinuxServer(
                hosts.SSHHost(server['addr'], port=int(server.get('port', 22))),
                server)

        # potential bg thread for ping untilstop
        self.ping_thread = None

        # potential bg thread for client network monitoring
        self.client_netdump_thread = None
        self.client_stats_thread = None
        self.__client_discover_commands(client)

        self.firewall_rules = []
        self.host_route_args = {}

        # interface name on client
        devs = self.__get_wlan_devs(self.client)
        if len(devs) == 0:
            raise error.TestFail('No wlan devices found on %s' % client['addr'])
        self.client_wlanif = client.get('wlandev', devs[0])
        self.client.wlan_mac = self.__get_interface_mac(self.client,
                                                        self.client_wlanif)

        # Make sure powersave mode is off by default.
        self.client_powersave_off([])

        # Synchronize time on all devices
        self.time_sync([])

        # Find all repeated steps and create iterators for them
        self.iterated_steps = {}
        step_names = [step[0] for step in steps]
        for step_name in list(set(step_names)):
            if step_names.count(step_name) > 1:
                self.iterated_steps[step_name] = 0

        self.run_options = config['run_options']
        if (config['router']['addr'] == config['server']['addr'] and
            'server_capture_all' in self.run_options):
            # Do not perform capture on the server if it is the same host
            # as the router.  Instead, use the 'router_capture_all' option
            # so the router instance can mediate phy usage.
            self.run_options.remove('server_capture_all')
            if 'router_capture_all' not in self.run_options:
                self.run_options.append('router_capture_all')

        self.command_hooks = {}

        if 'server_capture_all' in self.run_options:
            self.__add_hook('config', self.hosting_server.start_capture)
        if 'router_capture_all' in self.run_options:
            self.__add_hook('config', self.wifi.start_capture)
        if 'client_capture_all' in self.run_options:
            self.__add_hook('config', self.client_start_capture)
        if 'client_stats_all' in self.run_options:
            self.__add_hook('config', self.client_start_statistics)

        self.ethernet_mac_address = None
        string = self.__get_interface_mac(self.client, "eth0")
        if string:
          pieces = string.split(":")
          self.ethernet_mac_address = "".join(pieces)

        self.init_profile()
        self.client_capabilities = self.__get_client_capabilities()
        self.router_capabilities = self.__get_router_capabilities()


    @property
    def server(self):
        return self.hosting_server.server


    @property
    def server_wifi_ip(self):
        """ Returns an IP address for the client to ping. """
        if self.wifi.force_local_server:
            # Server WiFi IP is created using a local server address.
            return self.wifi.local_server_address(0)
        return self.hosting_server.wifi_ip


    def init_profile(self):
       # NB: do last so code above doesn't need to cleanup on failure
       self.test_profile = {'name':'test'}
       # cleanup in case a previous failure left the profile around
       self.profile_cleanup()
       self.profile_create(self.test_profile)
       self.profile_push(self.test_profile)


    def cleanup(self, params):
        """ Cleanup state: disconnect client and destroy ap """
        if 'no_cleanup_disconnect' not in self.run_options:
            self.disconnect({})
            self.wifi.destroy({})

        self.wifi.cleanup({})
        self.profile_cleanup()
        self.client_stop_capture({})
        self.client_stop_statistics({})
        self.firewall_cleanup({})
        self.host_route_cleanup({})
        self.wifi.stop_capture({})
        self.hosting_server.stop_capture({})


    def __client_discover_commands(self, client):
        self.client_cmd_netdump = client.get('cmd_netdump', 'tcpdump')
        self.client_cmd_ifconfig = client.get('cmd_ifconfig', 'ifconfig')
        self.client_cmd_iw = client.get('cmd_iw', 'iw')
        self.client_cmd_netperf = wifi_test_utils.must_be_installed(
                self.client, client.get('cmd_netperf_client',
                                        '/usr/local/bin/netperf'))
        self.client_cmd_netserv = wifi_test_utils.must_be_installed(
                self.client, client.get('cmd_netperf_server',
                                        '/usr/local/sbin/netserver'))
        self.client_cmd_iperf = wifi_test_utils.must_be_installed(
                self.client, client.get('cmd_iperf_client',
                                         '/usr/local/bin/iperf'))
        self.client_cmd_ip = wifi_test_utils.must_be_installed(
                self.client, client.get('cmd_ip',
                                        '/usr/local/sbin/ip'))
        self.client_cmd_iptables = '/sbin/iptables'
        self.client_cmd_flimflam_lib = client.get('flimflam_lib',
                                                  '/usr/local/lib/flimflam')
        self.client_cmd_ping = client.get('cmd_ping', 'ping')
        self.client_cmd_ping6 = client.get('cmd_ping6', 'ping6')
        self.client_cmd_wpa_cli = client.get('cmd_wpa_cli', 'wpa_cli')

    def __get_wlan_devs(self, host):
        ret = []
        result = host.run("%s dev" % self.client_cmd_iw)
        current_if = None
        for line in result.stdout.splitlines():
            ifmatch = re.search("Interface (\S*)", line)
            if ifmatch is not None:
                current_if = ifmatch.group(1)
            elif ('type managed' in line or 'type IBSS' in line) and current_if:
                ret.append(current_if)
        logging.info("Found wireless interfaces %s" % str(ret))
        return ret


    def __get_interface_mac(self, host, ifname):
        result = host.run("%s link show %s" % (self.client_cmd_ip, ifname))
        macmatch = re.search("link/ether (\S*)", result.stdout)
        if macmatch is not None:
            return macmatch.group(1)
        return None


    def __get_client_capabilities(self):
        caps = []

        # Find out if this device supports 5GHz
        system = site_linux_system.LinuxSystem(self.client, {}, '')
        if [freq for freq in system.phys_for_frequency.keys() if freq > 5000]:
            caps.append(WiFiTest._capability_5ghz)
        logging.info("Client system capabilities: %s" % repr(caps))
        return caps


    def __get_router_capabilities(self):
        caps = []

        # Find out if this device supports multi-AP
        system = site_linux_system.LinuxSystem(self.router, {}, '')
        phymap = system.phys_for_frequency
        frequencies = phymap.keys()
        if [freq for freq in frequencies if freq > 5000]:
            caps.append(WiFiTest._capability_5ghz)
        if [freq for freq in frequencies if len(phymap[freq]) > 1]:
            caps.append(WiFiTest._capability_multi_ap_same_band)
            caps.append(WiFiTest._capability_multi_ap)
        elif len(system.phy_bus_type) > 1:
            caps.append(WiFiTest._capability_multi_ap)
        logging.info("Router system capabilities: %s" % repr(caps))
        return caps


    def __get_step_requirements(self):
        # This finds out what additional requirements are implicit based on
        # the steps outlined in the test description.
        client_reqs = set()
        router_reqs = set()
        for step in self.steps:
            if len(step) < 2 or step[1].__class__ != dict:
                continue
            method = step[0]
            params = step[1]
            if method != 'config':
                continue
            if 'channel' in params and int(params['channel']) > 5000:
                client_reqs.add(WiFiTest._capability_5ghz)
                router_reqs.add(WiFiTest._capability_5ghz)
            if 'multi_interface' in params:
                router_reqs.add(WiFiTest._capability_multi_ap)
        logging.info("Step requirements: Client: %s, AP: %s" %
                     (repr(client_reqs), repr(router_reqs)))
        return list(client_reqs), list(router_reqs)


    def __add_hook(self, hook, fn):
        if hook not in self.command_hooks:
            self.command_hooks[hook] = []

        self.command_hooks[hook].append(fn)


    def __run_hooks(self, hook, params):
        if hook not in self.command_hooks:
            return

        for fn in self.command_hooks[hook]:
            if getattr(fn, 'im_class', None):
                hook_name = "%s.%s" % (fn.im_class.__name__, fn.__name__)
            else:
                hook_name = fn.__name__
            logging.info("%s: hook '%s' for method '%s' params %s", self.name,
                         hook_name, hook, params)
            fn(params)


    def run(self):
        """
        Run a WiFi test.  Each step is interpreted as a method either in this
        class or in one of the ancillary router or server classes and invoked
        with the supplied parameter dictionary.

        This routine bases its expectation of the method's result on the value
        (if any) of a prefix before the method name:

          - No prefix: The operation is expected to succeed.

          - '!': The operation is expected to fail; this is useful, for
            example, for testing parameter checking in flimflam.

          - '~': We don't care whether the operation succeeds or fails; this
            is especially useful during cleanup (e.g., deleting profiles).
        """
        for requirement in self.client_requirements:
            if not requirement in self.client_capabilities:
                raise error.TestNAError(
                    "%s: client is missing required capability: %s" %
                    (self.name, requirement))
        for requirement in self.router_requirements:
            if not requirement in self.router_capabilities:
                raise error.TestNAError(
                    "%s: AP is missing required capability: %s" %
                    (self.name, requirement))

        for step_number, s in enumerate(self.steps):
            method = s[0]
            if method[0] == '!':
                expect_result = WiFiTest._result_expect_failure
                method = method[1:]
            elif method[0] == '~':
                expect_result = WiFiTest._result_dont_care
                method = method[1:]
            else:
                expect_result = WiFiTest._result_expect_success
            if len(s) > 1:
                params = s[1]
            else:
                params = {}
            if len(s) > 2:
                failure_string = s[2]
            else:
                failure_string = None

            # What should perf data be prefixed with?
            if 'perf_prefix' in params:
                self.prefix = '%s_%s' % (method, params.pop('perf_prefix'))
            elif method in self.iterated_steps:
                self.prefix = '%s_%02d' % (method, self.iterated_steps[method])
                self.iterated_steps[method] += 1
            else:
                self.prefix = method

            self.__run_hooks(method, params)

            expectation = (" (expect failure)"
                           if expect_result is WiFiTest._result_expect_failure
                           else "")

            logging.info("-------------------------------------------")
            logging.info("%s: step %d '%s'%s params %s",
                         self.name, step_number+1, method, expectation, params)

            self.error_message = ''
            func = getattr(self, method, None)
            if func is None:
                func = getattr(self.wifi, method, None)
            if func is None:
                func = getattr(self.hosting_server, method, None)
            if func is None and self.attenuator:  # Must be an Attenuator method
                func = getattr(self.attenuator, method, None)

            if func is not None:
                try:
                    func(params)
                    if expect_result is WiFiTest._result_expect_failure:
                        # TODO(wdg): This should be rewritten so that we don't
                        # swap the expectation value of a succeeding test,
                        # here.  It's non-intuitive.
                        expect_result = WiFiTest._result_expect_success
                        raise error.TestFail("Succeeded (but expected "
                                             "failure).")
                except Exception, e:
                    if expect_result is WiFiTest._result_dont_care:
                        logging.info("%s: Failed (but we don't care).",
                                     self.name)
                        continue
                    elif expect_result is WiFiTest._result_expect_failure:
                        if not failure_string:
                            logging.info("%s: Failed (but we expected that).",
                                         self.name)
                            continue

                        # If test did not explicitly specify an error message,
                        # perhaps we can scoop one out of the exception
                        if not self.error_message and hasattr(e, 'result_obj'):
                            self.error_message = (e.result_obj.stderr +
                                                  e.result_obj.stdout)
                        if re.search(failure_string, self.error_message):
                            logging.info("%s: Failed (but we expected that).",
                                         self.name)
                            continue

                        logging.error("Expected failure, but error string does "
                                      "not match what was expected. Got %s but "
                                      "expected %s.",
                                      self.error_message,
                                      failure_string)
                    logging.error("%s: Step '%s' failed: %s; abort test",
                        self.name, method, str(e))
                    logging.info("===========================================")
                    self.cleanup({})
                    traceback.print_exc()
                    raise e
            else:
                logging.error("%s: Step '%s' unknown; abort test",
                    self.name, method)
                logging.info("===========================================")
                self.cleanup({})
                break
        else:
            logging.info("===========================================")
            # If all steps ran successfully perform the normal cleanup steps
            self.cleanup({})


    def write_keyvals(self, job):
        job.write_perf_keyval(self.perf_keyvals)

    def write_perf(self, data):
        for key, value in data.iteritems():
            if value is not None:
                self.perf_keyvals['%s_%s' % (self.prefix, key)] = value


    def __get_interface_addresses(self, host, ifname, ip_version):
        addresses = []
        result = host.run("%s -%d addr show dev %s" %
                          (self.client_cmd_ip, ip_version, ifname))
        for line in result.stdout.splitlines():
            addr_match = re.search("inet\S* (\S*)", line)
            if addr_match is not None:
                addresses.append(addr_match.group(1))
        return addresses


    def __get_ipaddr(self, host, ifnet):
        addrs = self.__get_interface_addresses(host, ifnet, 4)
        if not addrs:
             raise error.TestFail("No inet address found")
        return addrs[0].split('/')[0]


    def __get_ip6addrs(self, host, ifnet):
        return self.__get_interface_addresses(host, ifnet, 6)


    def __get_local_file(self, pattern):
        """
        Pass a string pattern with a "%...d" in it, and get back a unique
        string with the number of times this pattern has been used.  This
        is useful for creating unique local file names to store data
        related to each test run.
        """
        if not getattr(self, 'local_file_counts', None):
            self.local_file_counts = {}
        file_count = self.local_file_counts.get(pattern, 0)
        self.local_file_counts[pattern] = file_count + 1
        return './debug/%s' % (pattern % file_count)


    def install_script(self, script_name, *support_scripts):
        if script_name in self.client_installed_scripts:
            return self.client_installed_scripts[script_name]
        script_client_dir = self.client.get_tmp_dir()
        script_client_file = os.path.join(script_client_dir, script_name)
        for copy_file in [script_name] + list(support_scripts):
            # Look either relative to the current location of this file or
            # relative to ../client/common_lib/cros/site_wlan for the script.
            script_relative_paths = [['.'],
                                     ['..', 'client', 'common_lib',
                                      'cros', 'site_wlan']]
            for rel_path in script_relative_paths:
                src_file = os.path.join(
                    os.path.dirname(os.path.realpath(__file__)),
                    *(rel_path + [copy_file]))
                if os.path.exists(src_file):
                    break
            else:
                raise ScriptNotFound(copy_file)

            dest_file = os.path.join(script_client_dir,
                                     os.path.basename(src_file))
            self.client.send_file(src_file, dest_file, delete_dest=True)
        self.client_installed_scripts[script_name] = script_client_file
        return script_client_file

    def insert_file(self, host, filename, contents):
        """
        Send a byte string to a file on a remote host.

        @param host host object representing a remote machine.
        @param filename string path on remote machine to copy to.
        @param contents raw contents of the file to be created

        """
        # Write the contents to local disk first so we can use the easy
        # built in mechanism to do this.
        with tempfile.NamedTemporaryFile() as f:
            f.write(contents)
            f.flush()
            os.chmod(f.name, stat.S_IRUSR | stat.S_IWUSR |
                             stat.S_IRGRP | stat.S_IWGRP |
                             stat.S_IROTH | stat.S_IWOTH)
            host.send_file(f.name, filename, delete_dest=True)


    def install_files(self, params):
        """ Install files on the client or router with the provided
        contents"""

        systemname = params.get('system', None)
        if systemname == 'router':
            system = self.router
        elif systemname == 'client':
            system = self.client
        elif systemname == 'server':
            system = self.server
        else:
            raise error.TestFail('install_files: Must specify router, '
                                 'server or client')

        for name,contents in params.get('files', {}).iteritems():
            self.insert_file(system, name, contents)


    def __clean_tpm(self):
        self.client.run("initctl restart chapsd")
        cryptohome_cmd = "/usr/sbin/cryptohome"
        self.client.run(cryptohome_cmd + " --action=tpm_take_ownership",
                ignore_status = True)
        self.client.run(cryptohome_cmd + " --action=tpm_wait_ownership",
                ignore_status = True)


    def __load_tpm_token(self, token_auth):
        chaps_dir = "/tmp/chaps/"
        self.client.run("rm -rf " + chaps_dir)
        self.client.run("mkdir " + chaps_dir)
        self.client.run("chown %s:%s %s" % (
                "chaps",
                "chronos-access",
                chaps_dir))
        self.client.run("chaps_client --load --path=%s --auth=\"%s\"" % (
                chaps_dir,
                token_auth))

    def install_tpm_object(self, params):
        if not "data" in params:
            raise error.TestFail("Need a data parameter to install a TPM"
                                 "certificate")
        if not "id" in params:
            raise error.TestFail("Need an object id to install a TPM"
                                 "certificate")
        if not "object_type" in params:
            raise error.TestFail("Need to know whether the requested TPM "
                                 "object is a private key or a certificate.")
        if params["object_type"] == "cert":
            conv_cmd = "openssl x509 -in %s -inform PEM -out %s -outform DER"
            load_cmd = "p11_replay --import --path=%s --type=cert --id=%s"
        elif params["object_type"] == "key":
            conv_cmd = "openssl rsa -in %s -inform PEM -out %s -outform DER"
            load_cmd = "p11_replay --import --path=%s --type=privkey --id=%s"
        else:
            raise error.TestFail("Invalid object type, expected either cert "
                                 "or key.")
        data = params["data"]
        object_id = params["id"]
        pem_path = self.client.run("mktemp").stdout.strip()
        der_path = self.client.run("mktemp").stdout.strip()
        self.install_files({ "system":"client", "files":{ pem_path:data } } )
        # Convert those keys into DER format
        self.client.run(conv_cmd % (pem_path, der_path))
        # load that stuff into the TPM
        self.client.run(load_cmd % (der_path, object_id))


    def initialize_tpm(self, params):
        """ Remove past state from TPM, and install a new token so that we can
        later install objects to the TPM.  Call this function before calling
        install_tpm_object. """
        self.__clean_tpm()
        token_auth = site_eap_certs.auth_pin
        self.__load_tpm_token(token_auth)


    def install_nss_certificate(self, params):
        """ Install an PEM certifcate into the NSS database on the client. """
        if not 'data' in params:
            raise error.TestFail('Need a data parameter to install a NSS '
                                 'certificate')
        if not 'id' in params:
            raise error.TestFail('Need an object id to install an NSS '
                                 'certificate')

        data = params['data']
        object_id = params['id']
        pem_path = self.client.run('mktemp').stdout.strip()
        der_path = self.client.run('mktemp').stdout.strip()

        # Copy the PEM input certificate into a temporary file on the client.
        self.install_files({ 'system' : 'client',
                             'files' : { pem_path : data } } )

        # Convert the certificate into DER format
        self.client.run('openssl x509 -in %s -inform PEM -out %s -outform DER' %
                        (pem_path, der_path))
        # Load that stuff into the NSS database.
        self.client.run('nsscertutil -A -t P,, -i %s -n %s -d sql:%s' %
                        (der_path, object_id, site_eap_certs.nss_cert_db_path))
        # Make sure the NSS database remains accessible by the NSS user.
        self.client.run('chown -R %s: %s' %
                        (site_eap_certs.nss_cert_db_user,
                         site_eap_certs.nss_cert_db_path))
        # Cleanup.
        self.client.run('rm -f %s %s' % (pem_path, der_path))


    def initialize_nss(self, params):
        """ Initialize the NSS database on the client. """
        self.client.run('rm -rf %s' % site_eap_certs.nss_cert_db_path)
        self.client.run('mkdir -p %s' % site_eap_certs.nss_cert_db_path)
        self.client.run('echo "\n\n" | nsscertutil -N -d sql:%s' %
                        site_eap_certs.nss_cert_db_path)


    def connect(self, params):
        """ Connect client to AP/router """

        script_client_file = self.install_script('site_wlan_connect.py',
                                                 'site_wlan_dbus_setup.py',
                                                 'site_wlan_wait_state.py',
                                                 'constants.py')

        flags = []
        if params.get('debug', True):
            flags.append('--debug')
        if params.get('hidden', False):
            flags.append('--hidden')
        if 'mode' in params:
            flags.append('--mode=%s' % params['mode'])
        if params.get('nosave', False):
            flags.append('--nosave')

        result = self.client.run('python "%s" %s "%s" "%s" "%s" "%d" "%d"' %
            (script_client_file,
             ' '.join(flags),
             params.get('ssid', self.wifi.get_ssid()),
             params.get('security', ''),
             params.get('psk', ''),
             params.get('assoc_timeout', self.deftimeout),
             params.get('config_timeout', self.deftimeout))).stdout.rstrip()

        result_times = re.match('OK ([0-9\.]*) ([0-9\.]*) ([0-9\.]*) '
                                '([0-9\.]*) ([0-9]+) (\S+) (\w+) .*',
                                result)
        if not result_times:
            raise error.TestFail('Connect succeeded but result not parsed: ' +
                                 result)

        self.write_perf({'acquire_s'    : result_times.group(1),
                         'select_s'     : result_times.group(2),
                         'assoc_s'      : result_times.group(3),
                         'config_s'     : result_times.group(4),
                         'frequency'    : result_times.group(5)})
        for k in ('already_connected', 'clear_error', 'fast_fail',
                  'get_prop', 'in_progress', 'lost_dbus', 'multiple_attempts'):
            if re.search(k, result) is not None:
                self.write_perf({k:'true'})

        print "%s: %s" % (self.name, result)

        # stash connection state to emit for each test result
        self.cur_frequency = result_times.group(5)
        self.cur_phymode = result_times.group(6)
        self.cur_security = result_times.group(7)

        # fetch IP address of wireless device
        self.client_wifi_ip = self.__get_ipaddr(self.client, self.client_wlanif)
        logging.info("%s: client WiFi-IP is %s", self.name, self.client_wifi_ip)
        # TODO(sleffler) not right for non-mac80211 devices
        # TODO(sleffler) verify debugfs is mounted @ /sys/kernel/debug
        self.client_debugfs_path = "/sys/kernel/debug/ieee80211/%s/netdev:%s" \
            % ("phy0", self.client_wlanif)


    def disconnect(self, params):
        """ Disconnect previously connected client """

        self.client_ping_bg_stop({})

        script_client_file = self.install_script('site_wlan_disconnect.py',
                                                 'site_wlan_dbus_setup.py',
                                                 'constants.py')
        result = self.client.run('python "%s" "%s" "%d"' %
            (script_client_file,
            params.get('ssid', self.wifi.get_ssid()),
            params.get('wait_timeout', self.deftimeout))).stdout.rstrip()

        print "%s: %s" % (self.name, result)


    def profile(self, params):
        """ Display profile information -- for debugging. """

        print "\nSERVICES:"
        result = self.client.run('%s/test/list-services' %
                        (self.client_cmd_flimflam_lib),
                        ignore_status=True)
        print "%s: %s" % (self.name, result)

        print "\nENTRIES:"
        result = self.client.run('%s/test/profile list-entries' %
                        (self.client_cmd_flimflam_lib),
                        ignore_status=True)
        print "%s: %s" % (self.name, result)

    def client_check_profile_properties(self, params):
        """ Verify that profile/entries properties equal expected values. """

        args = ['--param %s:%s' % (var, val) for var, val in params.iteritems()]
        if self.ethernet_mac_address:
          args.append('--ethmac %s' % self.ethernet_mac_address)
        args.append('--command ClientCheckProfileProperties')

        script_client_file = self.install_script('site_wlan_profiles.py',
                                                 'site_wlan_dbus_setup.py',
                                                 'constants.py')

        result = self.client.run('python "%s" %s' %
             (script_client_file, ' '.join(args))).stdout.rstrip()

        print "%s: %s" % (self.name, result)

    def client_profile_delete_entry(self, params):
        """ Verify that profile/entries properties equal expected values. """

        args = ['--param %s:%s' % (var, val) for var, val in params.iteritems()]
        if self.ethernet_mac_address:
          args.append('--ethmac %s' % self.ethernet_mac_address)
        args.append('--command ClientProfileDeleteEntry')

        script_client_file = self.install_script('site_wlan_profiles.py',
                                                 'site_wlan_dbus_setup.py',
                                                 'constants.py')

        result = self.client.run('python "%s" %s' %
             (script_client_file, ' '.join(args))).stdout.rstrip()

        print "%s: %s" % (self.name, result)

    def __wait_service_start(self, params):
        """ Wait for service transitions on client. """

        script_client_file = self.install_script('site_wlan_wait_state.py',
                                                 'site_wlan_dbus_setup.py',
                                                 'constants.py')
        args = []

        # Whether to print out all state transitions of watched services to
        # stderr
        if params.get('debug', True):
            args.append('--debug')
        # Time limit on the execution of a single step
        if 'step_timeout' in params:
            args.append('--step_timeout %d' % int(params['step_timeout']))
        # Time limit to wait for a service to appear in the service list
        if 'service_timeout' in params:
            args.append('--svc_timeout %d' % int(params['service_timeout']))
        # Time limit on the execution of the entire series of steps
        args.append('--run_timeout=%d' % int(params.get('run_timeout', 10)))

        states = params.get('states', [])
        if not states:
            raise error.TestFail('No states given to wait for')

        for service, state in states:
            args.append('"%s=%s"' % (service or self.wifi.get_ssid(), state))

        self.wait_service_states = states
        return 'python "%s" %s' % (script_client_file, ' '.join(args))


    def __wait_service_complete(self, params, result):
        print "%s: %s" % (self.name, result)

        states = self.wait_service_states
        cstates = []
        counts = {}
        for service, state in states:
            cstate = state.strip('+-').replace(':', '_')
            cstates.append(cstate)
            if state in counts:
                counts[cstate] = 1
            else:
                counts[cstate] = 0

        for cstate, intr in zip(cstates, result.stdout.split(' ')):
            if intr.startswith('ERR_'):
                raise error.TestFail('Wait for step %s failed with error %s' %
                                     (cstate, intr))
            if counts[cstate]:
                index = '%s%d' % (cstate, counts[cstate] - 1)
                counts[cstate] += 1
            else:
                index = cstate

            self.write_perf({ index:float(intr) })
            print "  %s: %s" % (state, intr)

            max = 'max_' + cstate
            if max in params and float(intr) > float(params[max]):
                raise error.TestFail('Too long to reach %s state: %f > %f' %
                                     (cstate, float(intr), float(params[max])))


    def wait_service(self, params):
        result = self.client.run(self.__wait_service_start(params))
        self.__wait_service_complete(params, result)


    def wait_service_suspend_bg(self, params):
        params['after_command'] = self.__wait_service_start(params)
        self.client_suspend_bg(params)


    def wait_service_suspend_end(self, params):
        self.client_suspend_end(params)
        self.__wait_service_complete(params, self.client_suspend_thread.result)


    def client_powersave_on(self, params):
        """ Enable power save operation """
        self.client.run("iw dev %s set power_save on" % self.client_wlanif)


    def client_powersave_off(self, params):
        """ Disable power save operation """
        self.client.run("iw dev %s set power_save off" % self.client_wlanif)


    def client_check_powersave(self, params):
        """ Check status of power save mode """
        result = self.client.run("iw dev %s get power_save" %
                                 self.client_wlanif)
        output = result.stdout.rstrip()       # NB: chop \n
        # output should be either "Power save: on" or "Power save: off"
        find_re = re.compile('([^:]+):\s+(\w+)')
        find_results = find_re.match(output)
        want = params[0]
        if not find_results:
            raise error.TestFail("wanted %s but not found" % want)
        got = find_results.group(2)
        if got != want:
            raise error.TestFail("client_check_powersave: wanted %s got %s" %
                                 (want, got))


    def __client_check(self, param, want):
        """ Verify negotiated station mode parameter """
        result = self.client.run("cat '%s/%s'" %
            (self.client_debugfs_path, param))
        got = result.stdout.rstrip()       # NB: chop \n
        if got != want:
            raise error.TestFail("client_check_%s: wanted %s got %s" %
                                 (param, want, got))


    def __client_check_iw_link(self, param, want):
        """ Verify negotiated station mode parameter """
        result = self.client.run("%s dev %s link" %
                                 (self.client_cmd_iw, self.client_wlanif))
        find_re = re.compile("\s*%s:\s*(.*\S)\s*$" % param)
        find_results = filter(bool, map(find_re.match,
                                        result.stdout.splitlines()))
        if not find_results:
            raise error.TestFail("wanted %s but %s not found" % (want, param))
        got = find_results[0].group(1)
        if not re.match(want, got):
            raise error.TestFail("wanted %s got %s" % (want, got))

    def client_check_bintval(self, params):
        """ Verify negotiated beacon interval """
        self.__client_check_iw_link("beacon int", params[0])


    def client_check_dtimperiod(self, params):
        """ Verify negotiated DTIM period """
        self.__client_check_iw_link("dtim period", params[0])


    def client_check_rifs(self, params):
        """ Verify negotiated RIFS setting """
        self.__client_check("rifs", params[0])


    def client_check_shortgi20(self, params):
        """ Verify negotiated Short GI setting """
        self.__client_check("sgi20", params[0])


    def client_check_shortgi40(self, params):
        """ Verify negotiated Short GI setting """
        self.__client_check("sgi40", params[0])


    def client_check_shortslot(self, params):
        """ Verify negotiated Short Slot setting """
        self.__client_check("short_slot", params[0])


    def client_check_protection(self, params):
        """ Verify negotiated CTS protection setting """
        self.__client_check("cts_prot", params[0])


    def client_monitor_start(self, params):
        """ Start monitoring system events """
        raise NotImplementedError("client_monitor_start")


    def client_monitor_stop(self, params):
        """ Stop monitoring system events """
        raise NotImplementedError("client_monitor_stop")


    def client_check_event_mic(self, params):
        """ Check for MIC error event """
        raise NotImplementedError("client_check_event_mic")


    def client_check_event_countermeasures(self, params):
        """ Check for WPA CounterMeasures event """
        raise NotImplementedError("client_check_event_countermeasures")


    def client_check_frequency(self, params):
        """ Verify current frequency """
        self.__client_check_iw_link("freq", params[0])


    def client_check_service_properties(self, params):
        """ Verify that service properties attained their expected values. """
        service = params.pop("service", None)
        if self.ethernet_mac_address and service == "ethernet":
          service = "ethernet_%s" % self.ethernet_mac_address
        states = [(service, "%s:%s" % (var, val))
                  for var, val in params.iteritems()]
        self.wait_service({ "run_timeout": 0, "states": states})

    def sleep(self, params):
        time.sleep(float(params['time']))


    def __unreachable(self, method):
        logging.info("%s: SKIP step %s; server is unreachable",
            self.name, method)


    def __get_pingstats(self, ping_output):
        stats = wifi_test_utils.parse_ping_output(ping_output)
        stats['frequency'] = self.cur_frequency
        stats['phymode']   = self.cur_phymode
        stats['security']  = self.cur_security
        return stats


    def __print_pingstats(self, label, stats):
        logging.info("%s: %s%s/%s, %s%% loss, rtt %s/%s/%s",
            self.name, label, stats['xmit'], stats['recv'], stats['loss'],
             stats['min'], stats['avg'], stats['max'])


    def iw_event_scan(self, params):
        """ Obtain the event scan output and store it

        Params:
            duration: Indicates time in seconds.  If no duration
                      provided, iw even runs until iw_even_scan_stop
                      is called.
        """
        duration = params.get('duration', 0)
        cmd = '%s event -f' % self.client_cmd_iw
        self.iw_event_thread = remote_command.Command(self.client, cmd)

        if duration:
            time.sleep(float(duration))
            self.iw_event_thread_stop({})


    def iw_event_scan_stop(self, params):
        """ Stops the iw event thread """
        self.iw_event_thread.join()
        self.iw_event_thread_output = self.iw_event_thread.result.stdout
        logging.debug('Output of iw scan is %s' % self.iw_event_thread_output)


    def search_iw_events(self, params):
        """ Searches through the last run iw event scan for strings

        Params:
            match: A list of strings to match.

        Raises:
            error.TestFail if any strings in match are not found in
                iw event output.
        """
        match_list = params.get('match', [])
        if not hasattr(self, 'iw_event_thread_output'):
            return

        for match in match_list:
            if match not in self.iw_event_thread_output:
                raise error.TestFail("Expecting %s in iw event output but "
                               "it wasn't present.")


    def client_ping(self, params):
        """ Ping the server from the client """
        if 'ping_ip' in params:
            ping_ip = params['ping_ip']
        else:
            if 'dest' in params:
                ping_dest = params['dest']
            else:
                if self.wifi.has_local_server():
                    ping_dest = 'router'
                else:
                    ping_dest = 'server'

            if ping_dest == 'server':
                ping_ip = self.server_wifi_ip
            elif ping_dest == 'router':
                ping_ip = self.wifi.get_wifi_ip(params.get('ap', 0))
            else:
                raise error.TestFail('Unknown ping destination "%s"' %
                                     ping_dest)
        count = params.get('count', self.defpingcount)
        # set timeout for 3s / ping packet
        result = self.client.run("%s %s %s" % (
            self.client_cmd_ping, wifi_test_utils.ping_args(params), ping_ip),
                                 timeout=3*int(count))

        stats = self.__get_pingstats(result.stdout)
        if "save_stats" in params:
            self.ping_stats[params["save_stats"]] = stats
        self.write_perf(stats)
        self.__print_pingstats("client_ping ", stats)


    def client_ping_bg(self, params):
        """ Ping the server from the client """
        ping_ip = params.get('ping_ip', self.server_wifi_ip)
        cmd = "%s %s %s" % \
            (self.client_cmd_ping, wifi_test_utils.ping_args(params), ping_ip)
        self.ping_thread = remote_command.Command(self.client, cmd)


    def client_ping_bg_stop(self, params):
        if self.ping_thread is None:
            logging.info("Tried to stop a bg ping, but none was started")
            return
        # Sending SIGINT gives us stats at the end, how nice.
        self.ping_thread.join(signal.SIGINT)
        if "save_stats" in params:
            stats = self.__get_pingstats(self.ping_thread.result.stdout)
            self.ping_stats[params["save_stats"]] = stats
        self.ping_thread = None


    def assert_ping_similarity(self, params):
        """ Assert that two specified sets of ping parameters are 'similar' """
        if "stats0" not in params or "stats1" not in params:
            raise error.TestFail("Missing ping statistics keys")
        stats0 = self.ping_stats[params["stats0"]]
        stats1 = self.ping_stats[params["stats1"]]
        if "dev" not in stats0 or "dev" not in stats1:
            raise error.TestFail("Missing standard dev from ping stats")
        if "min" not in stats0 or "min" not in stats1:
            raise error.TestFail("Missing max rtt from ping stats")
        if "avg" not in stats0 or "avg" not in stats1:
            raise error.TestFail("Missing avg rtt from ping stats")
        if "max" not in stats0 or "max" not in stats1:
            raise error.TestFail("Missing max rtt from ping stats")
        avg0 = float(stats0["avg"])
        max0 = float(stats0["max"])
        avg1 = float(stats1["avg"])
        max1 = float(stats1["max"])
        # This check is meant to assert that ping latency remains 'similar'
        # during WiFi background scans.  APs typically send beacons every 100ms,
        # (the period is configurable) so bgscan algorithms like to sit in a
        # channel for 100ms to see if they can catch a beacon.
        #
        # Assert that the maximum latency is under 200 ms + whatever the
        # average was for the other sample.  This allows us to go off chanel,
        # but forces us to serve some real traffic when we go back on.
        # We'll do this check symmetrically because we don't actually know
        # which is the control distribution and which is the potentially dirty
        # distribution.
        if max0 > 200 + avg1 or max1 > 200 + avg0:
            logging.error(
                    "Ping0 min/avg/max/dev = {0}/{1}/{2}/{3}".format(
                        stats0["min"],
                        stats0["avg"],
                        stats0["max"],
                        stats0["dev"],
                        )
                    )
            logging.error(
                    "Ping1 min/avg/max/dev = {0}/{1}/{2}/{3}".format(
                        stats1["min"],
                        stats1["avg"],
                        stats1["max"],
                        stats1["dev"],
                        )
                    )
            raise error.TestFail("Significant difference in rtt due to bgscan")


    def server_ping(self, params):
        """ Ping the client from the server """
        ping_ip = params.get('ping_ip', self.client_wifi_ip)
        count = params.get('count', self.defpingcount)
        stats = self.hosting_server.ping(ping_ip, count, params)
        self.write_perf(stats)
        self.__print_pingstats("server_ping ", stats)


    def server_ping_bg(self, params):
        """ Ping the client from the server """
        ping_ip = params.get('ping_ip', self.client_wifi_ip)
        self.hosting_server.ping_bg(ping_ip, params)


    def server_ping_bg_stop(self, params):
        self.hosting_server.ping_bg_stop()


    def client_ping6(self, params):
        """ Ping the server from the client via IPv6 """
        if 'ping_ip' in params:
            ping_ip = params['ping_ip']
        else:
            result = self.client.run('%s -6 route show dev %s default' %
                                     (self.client_cmd_ip, self.client_wlanif))
            router_match = re.search('via (\S*)', result.stdout)
            if not router_match:
                raise error.TestFail('Cannot find default router')
            ping_ip = router_match.group(1)
            params.setdefault('interface', self.client_wlanif)
        count = params.get('count', self.defpingcount)
        # set timeout for 3s / ping packet
        result = self.client.run("%s %s %s" % (
            self.client_cmd_ping6, wifi_test_utils.ping_args(params), ping_ip),
            timeout=3*int(count))

        stats = self.__get_pingstats(result.stdout)
        self.write_perf(stats)
        self.__print_pingstats("client_ping6 ", stats)


    def __run_iperf(self, mode, params):
        """ Executes iperf w/ user-specified command-line options

        Caller is responsible for passing in correct options. Otherwise a test
        error would be raised.
        """
        iperf_args = ""
        if 'udp' in params:
            iperf_args += " -u"
            test = "UDP"
        else:
            test = "TCP"
        if 'nodelay' in params:
            iperf_args += " -N"
            self.write_perf({'nodelay':'true'})
        if 'window' in params:
            iperf_args += " -w %s" % params['window']
            self.write_perf({'window':params['window']})
        if 'bufsize' in params:  # Set buffer size in bytes
            iperf_args += " -l %s" % params['bufsize']
            self.write_perf({'bufsize':params['bufsize']})
        iperf_args += " -p %s" % self.defiperfport

        # Assemble client-specific arguments
        test_time = params.get('test_time', 15)
        client_args = iperf_args + " -f m -t %s" % test_time
        if 'bandwidth' in params:
            client_args += " -b %s" % params['bandwidth']
            self.write_perf({'bandwidth':params['bandwidth']})
        elif 'udp' in params:
            bw = None
            # Supply nominal channel bandwidth
            if self.cur_phymode == '802.11b':
                bw = '7m'
            elif self.cur_phymode == '802.11a':
                bw = '30m'              # assumes no bursting
            elif self.cur_phymode == '802.11g':
                bw = '30m'              # assumes no bursting
            elif self.cur_phymode == '802.11n':
                # TODO(sleffler) distinguish HT20/HT40 and # streams
                bw = '110m'
            if bw is not None:
                client_args += " -b %s" % bw
                self.write_perf({'bandwidth':bw})

        ip_rules = []
        if mode == 'server':
            server = { 'host': self.client, 'cmd': self.client_cmd_iperf }
            client = { 'host': self.server,
                       'cmd': self.hosting_server.cmd_iperf,
                       'target': self.client_wifi_ip }

            # Open up access from the server into our DUT
            ip_rules.append(self.__firewall_open('tcp', self.server_wifi_ip))
            ip_rules.append(self.__firewall_open('udp', self.server_wifi_ip))
        else:  # mode == 'client'
            server = { 'host': self.server,
                       'cmd': self.hosting_server.cmd_iperf }
            client = { 'host': self.client, 'cmd': self.client_cmd_iperf,
                       'target': self.server_wifi_ip }

        iperf_thread = remote_command.Command(server['host'],
            "%s -s %s" % (server['cmd'], iperf_args))
        # NB: block to allow server time to startup
        time.sleep(self.defwaittime)

        # Run iperf command and receive command results
        t0 = time.time()
        # Set timeout to be twice the test_time
        results = client['host'].run("%s -c %s%s" % \
            (client['cmd'], client['target'], client_args),
            timeout=2*int(test_time))
        actual_time = time.time() - t0
        logging.info('actual_time: %f', actual_time)

        iperf_thread.join()

        # Close up whatever firewall rules we created for iperf
        for rule in ip_rules:
            self.__firewall_close(rule)

        self.write_perf({
            'attenuation': self.cur_attenuation or 'unknown',
            'frequency'  : self.cur_frequency,
            'phymode'    : self.cur_phymode,
            'security'   : self.cur_security,
            'test'       : test,
            'mode'       : mode,
            'actual_time': actual_time,
        })

        logging.info(results)

        lines = results.stdout.splitlines()

        # Each test type has a different form of output
        if test in ['TCP', 'TCP_NODELAY']:
            """Parses the following and returns a singleton containing
            throughput.

            ------------------------------------------------------------
            Client connecting to localhost, TCP port 5001
            TCP window size: 49.4 KByte (default)
            ------------------------------------------------------------
            [  3] local 127.0.0.1 port 57936 connected with 127.0.0.1 port 5001
            [ ID] Interval       Transfer     Bandwidth
            [  3]  0.0-10.0 sec  2.09 GBytes  1.79 Gbits/sec
            """
            tcp_tokens = lines[6].split()
            if len(tcp_tokens) >= 6 and tcp_tokens[-1].endswith('bits/sec'):
                self.write_perf({'throughput':float(tcp_tokens[-2])})
        elif test in ['UDP', 'UDP_NODELAY']:
            """Parses the following and returns a tuple containing throughput
            and the number of errors.

            ------------------------------------------------------------
            Client connecting to localhost, UDP port 5001
            Sending 1470 byte datagrams
            UDP buffer size:   108 KByte (default)
            ------------------------------------------------------------
            [  3] local 127.0.0.1 port 54244 connected with 127.0.0.1 port 5001
            [ ID] Interval       Transfer     Bandwidth
            [  3]  0.0-10.0 sec  1.25 MBytes  1.05 Mbits/sec
            [  3] Sent 893 datagrams
            [  3] Server Report:
            [ ID] Interval       Transfer     Bandwidth       Jitter   Lost/Total Datagrams
            [  3]  0.0-10.0 sec  1.25 MBytes  1.05 Mbits/sec  0.032 ms    1/  894 (0.11%)
            [  3]  0.0-15.0 sec  14060 datagrams received out-of-order
            """
            # Search for the last row containing the word 'Bytes'
            mb_row = [row for row,data in enumerate(lines)
                      if 'Bytes' in data][-1]
            udp_tokens = lines[mb_row].replace('/', ' ').split()
            # Find the column ending with "...Bytes"
            mb_col = [col for col,data in enumerate(udp_tokens)
                      if data.endswith('Bytes')]
            if len(mb_col) > 0 and len(udp_tokens) >= mb_col[0] + 9:
                # Make a sublist starting after the column named "MBytes"
                stat_tokens = udp_tokens[mb_col[0]+1:]
                self.write_perf({'throughput':float(stat_tokens[0]),
                                 'jitter':float(stat_tokens[3]),
                                 'lost':float(stat_tokens[7].strip('()%'))})
        else:
            raise error.TestError('Unhandled test')

        return True


    def client_iperf(self, params):
        """ Run iperf on the client against the server """
        self.__run_iperf('client', params)


    def server_iperf(self, params):
        """ Run iperf on the server against the client """
        self.__run_iperf('server', params)


    def set_attenuation(self, params):
        """ Record current attenuation value """
        self.cur_attenuation = self.attenuator.set_attenuation(params)

    def _parse_attenuation(self, params):
        """ Sanity check attenuation values and make simple corrections """
        # Attenuations are measured in units of dB
        fixed_atten = params.get('fixed_atten', None)
        start_atten = params.get('start_atten', fixed_atten)
        end_atten = params.get('end_atten', None)

        if ((fixed_atten is None) or (start_atten is None) or
            (end_atten is None)):
            err = ('Please specify all attenuation values for this test: '
                   'fixed_atten, start_atten, end_atten.')
            raise error.TestFail(err)

        fixed_atten = int(fixed_atten)
        start_atten = int(start_atten)
        end_atten = int(end_atten)

        if start_atten < fixed_atten:
            logging.warning('start_atten (%d) reset to fixed_atten (%d)',
                            start_atten, fixed_atten)
            start_atten = fixed_atten
        if end_atten < start_atten:
            logging.warning('end_atten (%d) reset to start_atten (%d)',
                            end_atten, start_atten)
            end_atten = start_atten
        return fixed_atten, start_atten, end_atten


    def _parse_iperf_options(self, params):
        """ Parse iperf options and set reasonable defaults """
        proto = params.get('proto', 'udp')
        iperf_params = {
            proto: None,
            'test_time': params.get('test_time', '60'),
            'bufsize': params.get('bufsize', '1500'),
            }
        if proto == 'udp':
            iperf_params['bandwidth'] = params.get('bandwidth', '150M')
        else:
            iperf_params['window'] = params.get('window', '512K')
        return proto, iperf_params


    def rvr_test(self, params):
        """ Run rate vs. range tests using a variable attenuator """
        if self.attenuator is None:
            raise error.TestFail(
                'No variable attenuator specified for this test.')

        fixed_atten, start_atten, end_atten = self._parse_attenuation(params)
        proto, iperf_params = self._parse_iperf_options(params)

        atten_step = params.get('atten_step', 2)
        # Pad 1 to end_atten to ensure it's not excluded by range(), e.g.
        #   input: start_atten = 60, end_atten = 70, atten_step = 2
        #   output with padding = [60, 62, 64, 66, 68, 70]  (desired)
        #   output without padding = [60, 62, 64, 66, 68]  (probabaly undesired)
        atten_sequence = range(start_atten, end_atten+1, atten_step)
        for step_number, atten in enumerate(atten_sequence):
            for port in [0, 1]:  # Grover testbed uses ports 0 and 1
                self.set_attenuation(dict(va_port=port, fixed_atten=fixed_atten,
                                          total_atten=atten))
            iperf_params['attenuation'] = self.cur_attenuation
            self.sleep(dict(time='5'))  # Wait 5 seconds for config to propagate

            # Set iteration prefix for write_perf() to use
            self.prefix = 'rvr_%s_%d' % (proto, step_number)
            self.server_iperf(iperf_params)


    def __firewall_open(self, proto, src):
        rule = 'INPUT -s %s/32 -p %s -m %s -j ACCEPT' % (src, proto, proto)
        result = self.client.run('%s -S INPUT' % self.client_cmd_iptables)
        if '-A %s ' % rule in result.stdout.splitlines():
            return None
        self.client.run('%s -A %s' % (self.client_cmd_iptables, rule))
        self.firewall_rules.append(rule)
        return rule


    def __firewall_close(self, rule):
        if rule in self.firewall_rules:
            self.client.run('%s -D %s' % (self.client_cmd_iptables, rule))
            self.firewall_rules.remove(rule)

    def firewall_cleanup(self, params):
        for rule in self.firewall_rules:
            self.__firewall_close(rule)

    def __run_netperf(self, mode, params):
        np_rules = []
        if mode == 'server':
            server = { 'host': self.client, 'cmd': self.client_cmd_netserv }
            client = { 'host': self.server,
                       'cmd': self.hosting_server.cmd_netperf,
                       'target': self.client_wifi_ip }

            # Open up access from the server into our DUT
            np_rules.append(self.__firewall_open('tcp', self.server_wifi_ip))
            np_rules.append(self.__firewall_open('udp', self.server_wifi_ip))
        else:
            server = { 'host': self.server,
                       'cmd': self.hosting_server.cmd_netserv }
            client = { 'host': self.client, 'cmd': self.client_cmd_netperf,
                       'target': self.server_wifi_ip }

        netperf_thread = remote_command.Command(server['host'],
            "%s -p %s" % (server['cmd'],  self.defnetperfport))
        # NB: block to allow server time to startup
        time.sleep(self.defwaittime)

        # Assemble arguments for client command
        test = params.get('test', 'TCP_STREAM')
        netperf_args = '-H %s -p %s -t %s -l %d' % (client['target'],
                        self.defnetperfport, test, params.get('test_time', 15))

        # Run netperf command and receive command results
        t0 = time.time()
        results = client['host'].run("%s %s" % (client['cmd'], netperf_args))
        actual_time = time.time() - t0
        logging.info('actual_time: %f', actual_time)

        netperf_thread.join()

        # Close up whatever firewall rules we created for netperf
        for rule in np_rules:
            self.__firewall_close(rule)

        self.write_perf({
            'frequency'  : self.cur_frequency,
            'phymode'    : self.cur_phymode,
            'security'   : self.cur_security,
            'test'       : test,
            'mode'       : mode,
            'actual_time': actual_time,
        })

        logging.info(results)

        lines = results.stdout.splitlines()

        # Each test type has a different form of output
        if test in ['TCP_STREAM', 'TCP_MAERTS', 'TCP_SENDFILE']:
            """Parses the following (works for both TCP_STREAM, TCP_MAERTS and
            TCP_SENDFILE) and returns a singleton containing throughput.

            TCP STREAM TEST from 0.0.0.0 (0.0.0.0) port 0 AF_INET to \
            foo.bar.com (10.10.10.3) port 0 AF_INET
            Recv   Send    Send
            Socket Socket  Message  Elapsed
            Size   Size    Size     Time     Throughput
            bytes  bytes   bytes    secs.    10^6bits/sec

            87380  16384  16384    2.00      941.28
            """
            self.write_perf({'Throughput':float(lines[6].split()[4])})
        elif test == 'UDP_STREAM':
            """Parses the following and returns a touple containing throughput
            and the number of errors.

            UDP UNIDIRECTIONAL SEND TEST from 0.0.0.0 (0.0.0.0) port 0 AF_INET \
            to foo.bar.com (10.10.10.3) port 0 AF_INET
            Socket  Message  Elapsed      Messages
            Size    Size     Time         Okay Errors   Throughput
            bytes   bytes    secs            #      #   10^6bits/sec

            129024   65507   2.00         3673      0     961.87
            131072           2.00         3673            961.87
            """
            udp_tokens = lines[5].split()
            self.write_perf({'Throughput':float(udp_tokens[5]),
                             'Errors':float(udp_tokens[4])})
        elif test in ['TCP_RR', 'TCP_CRR', 'UDP_RR']:
            """Parses the following which works for both rr (TCP and UDP)
            and crr tests and returns a singleton containing transfer rate.

            TCP REQUEST/RESPONSE TEST from 0.0.0.0 (0.0.0.0) port 0 AF_INET \
            to foo.bar.com (10.10.10.3) port 0 AF_INET
            Local /Remote
            Socket Size   Request  Resp.   Elapsed  Trans.
            Send   Recv   Size     Size    Time     Rate
            bytes  Bytes  bytes    bytes   secs.    per sec

            16384  87380  1        1       2.00     14118.53
            16384  87380
            """
            self.write_perf({'Transfer_Rate':float(lines[6].split()[5])})
        else:
            raise error.TestError('Unhandled test')

        return True


    def client_netperf(self, params):
        """ Run netperf on the client against the server """
        self.__run_netperf('client', params)


    def server_netperf(self, params):
        """ Run netperf on the server against the client """
        self.__run_netperf('server', params)


    def __create_netdump_dev(self, devname='mon0'):
        self.client.run("%s dev %s del" % (self.client_cmd_iw, devname),
                        ignore_status=True)
        self.client.run("%s dev %s interface add %s type monitor" %
                        (self.client_cmd_iw, self.client_wlanif, devname))
        self.client.run("%s %s up" % (self.client_cmd_ifconfig, devname))
        return devname


    def __destroy_netdump_dev(self, devname='mon0'):
        self.client.run("%s dev %s del" % (self.client_cmd_iw, devname))


    def client_start_capture(self, params):
        """ Start capturing network traffic on the client """
        self.client_stop_capture({})
        devname = self.__create_netdump_dev()
        self.client_netdump_dir = self.client.get_tmp_dir()
        self.client_netdump_file = os.path.join(self.client_netdump_dir,
                                                "client.pcap")
        cmd = "%s -i %s -w %s -s %s" % (self.client_cmd_netdump, devname,
                                  self.client_netdump_file,
                                  params.get('snaplen', '0'))
        logging.info(cmd)
        self.client_netdump_thread = remote_command.Command(self.client, cmd)


    def client_stop_capture(self, params):
        if self.client_netdump_thread is not None:
            self.__destroy_netdump_dev()
            self.client_netdump_thread.join()
            self.client_netdump_thread = None
            self.client.get_file(
                self.client_netdump_file,
                self.__get_local_file('client_capture_%02d.pcap'))
            self.client.delete_tmp_dir(self.client_netdump_dir)
        else:
            # Just in case something got leftover from a previous run...
            self.client.run("pkill %s" % self.client_cmd_netdump,
                            ignore_status=True)


    def client_suspend(self, params):
        """ Suspend the system """

        script_client_file = self.install_script('site_system_suspend.py',
                                                 '../client/cros/rtc.py',
                                                 '../client/cros/'
                                                 'sys_power.py',
                                                 '../client/cros/'
                                                 'upstart.py')
        result = self.client.run('python "%s" %d' %
            (script_client_file, int(params.get("suspend_time", 5))))


    def client_suspend_bg(self, params):
        """ Suspend the system in the background """

        script_client_file = self.install_script('site_system_suspend.py',
                                                 '../client/cros/rtc.py',
                                                 '../client/cros/'
                                                 'sys_power.py',
                                                 '../client/cros/'
                                                 'upstart.py')
        cmd = ('python "%s" %d %s' %
               (script_client_file,
                int(params.get("suspend_time", 5)),
                params.get("after_command", '')))
        self.client_suspend_thread = remote_command.Command(self.client, cmd)


    def client_suspend_end(self, params):
        """ Join the backgrounded suspend thread """

        self.client_suspend_thread.join()
        if self.client_suspend_thread.result.exit_status:
            raise error.TestError('suspend failed')

    def restart_supplicant(self, params):
        """ Restart wpa_supplicant.  Cert params are unfortunately "sticky". """

        self.client.run("stop wpasupplicant; start wpasupplicant")


    def profile_create(self, params):
        """ Create a profile with the specified name """
        self.client.run('%s/test/profile create %s' %
                        (self.client_cmd_flimflam_lib, params['name']))
        self.created_profiles.append(params['name'])

    def profile_remove(self, params, ignore_status=False):
        """ Remove the specified profile """
        self.client.run('%s/test/profile remove %s' %
                        (self.client_cmd_flimflam_lib, params['name']),
                         ignore_status=ignore_status)

    def profile_push(self, params):
        """ Push the specified profile on the stack """
        self.client.run('%s/test/profile push %s' %
                        (self.client_cmd_flimflam_lib, params['name']))

    def profile_pop(self, params, ignore_status=False):
        """ Pop the specified profile from the stack or any profile
            if no name is specified.
        """
        if 'name' in params:
            self.client.run('%s/test/profile pop %s' %
                            (self.client_cmd_flimflam_lib, params['name']),
                            ignore_status=ignore_status)
        else:
            self.client.run('%s/test/profile pop' %
                            (self.client_cmd_flimflam_lib),
                            ignore_status=ignore_status)


    def profile_cleanup(self):
        """ Cleanup all profiles """
        # Pop and remove all profiles on the stack until 'default' is found.
        self.client.run('%s/test/profile clean' %
                        (self.client_cmd_flimflam_lib))
        # Some profiles may still in profile storage but not on the stack,
        # invoke 'profile_remove' for self.created_profiles to make sure that
        # all profiles are deleted.
        for profile_name in self.created_profiles:
            self.profile_remove({'name':profile_name}, ignore_status=True)

    def __get_wifi_device_path(self):
        if self.client_wifi_device_path:
            return self.client_wifi_device_path
        ret = []
        result = self.client.run('%s/test/list-devices' %
                                 self.client_cmd_flimflam_lib)
        device_path = None
        for line in result.stdout.splitlines():
            m = re.match('\[\s*(\S*)\s*\]', line)
            if m is not None:
                device_path = m.group(1)
                continue
            if re.search('Name = Wireless', line) is not None:
                self.client_wifi_device_path = device_path
                break

        return self.client_wifi_device_path

    def enable_wifi(self, params):
        wifi = self.__get_wifi_device_path()
        if wifi:
            self.client.run('%s/test/enable-device %s' %
                            (self.client_cmd_flimflam_lib, wifi))

    def disable_wifi(self, params):
        wifi = self.__get_wifi_device_path()
        if wifi:
            self.client.run('%s/test/disable-device %s' %
                            (self.client_cmd_flimflam_lib, wifi))


    def client_get_signal(self, params):
        result = self.client.run('%s dev %s link; '
                                 '%s dev %s station dump; '
                                 '%s dev %s survey dump' %
                                 ((self.client_cmd_iw, self.client_wlanif) * 3))
        current_frequency = None
        link_frequency = None
        signal_info = {}
        signal_values = ( 'frequency', 'signal', 'signal avg', 'noise' )
        for line in result.stdout.splitlines():
            m = re.match('\s*(\S.*):\s*(\S*)', line)
            if m is None:
                continue
            var, val = m.groups()
            if var == 'freq':
                link_frequency = val
            elif var == 'frequency':
                current_frequency = val
            if (var in signal_values and
                (current_frequency == None or
                 current_frequency == link_frequency)):
                signal_info[var] = val

        self.client_signal_info = signal_info
        logging.info('Signal Info: %s' % repr(signal_info))


    def bgscan_set(self, params):
        """ Control wpa_supplicant bgscan """
        opts = ""
        if params.get('short_interval', None):
            opts += " BgscanShortInterval=%s" % params['short_interval']
        if params.get('long_interval', None):
            opts += " ScanInterval=%s" % params['long_interval']
        if params.get('signal', None):
            signal = params['signal']
            if signal == 'auto':
                if 'signal avg' not in self.client_signal_info:
                    raise error.TestError('No signal info')
                else:
                    signal = int(self.client_signal_info['signal avg'])
                    if 'offset' in params:
                        signal += int(params['offset'])
                    if 'noise' in self.client_signal_info:
                        # Compensate for real noise vs standard estimate
                        signal -= 95 + int(self.client_signal_info['noise'])
                logging.info('Auto signal: %s' % repr(signal))
            opts += " BgscanSignalThreshold=%s" % signal
        if params.get('method', None):
            opts += " BgscanMethod=%s" % params['method']
        self.client.run('%s/test/set-bgscan --interface %s %s' %
                        (self.client_cmd_flimflam_lib, self.client_wlanif,
                         opts))


    def bgscan_disable(self, params):
        """ Disable wpa_supplicant bgscan """
        self.bgscan_set({'method' : 'none'})


    def bgscan_enable(self, params):
        """ Enable wpa_supplicant bgscan """
        self.bgscan_set({'method' : 'default'})


    def scan(self, params):
        scan_params = ''
        frequencies = params.get('freq', [])
        if frequencies:
           scan_params += ' freq %s' % ' '.join(frequencies)
        ssids = params.get('ssid', [])
        if ssids:
           scan_params += ' ssid "%s"' % '" "'.join(ssids)
        result = self.client.run("%s dev %s scan%s" %
                                 (self.client_cmd_iw, self.client_wlanif,
                                  scan_params))
        scan_lines = result.stdout.splitlines()
        for ssid in ssids:
            if ssid and ('\tSSID: %s' % ssid) not in scan_lines:
                raise error.TestFail('SSID %s is not in scan results: %s' %
                                     (ssid, result.stdout))


    def time_sync(self, params):
        for name in params or ['client', 'server', 'router']:
            system = { 'client': self.client,
                       'server': self.server,
                       'router': self.router }.get(name)
            epoch_seconds = time.time()
            busybox_format = '%Y%m%d%H%M.%S'
            busybox_date = datetime.datetime.utcnow().strftime(busybox_format)
            system.run('date -u --set=@%s 2>/dev/null || date -u %s' % \
                (epoch_seconds, busybox_date))

    def vpn_client_load_tunnel(self, params):
        """ Load the 'tun' device.

            Necessary when the VPN Server is configured with 'dev tun'.
        """
        result = self.client.run('modprobe tun') # When server using tunnel.

    def vpn_client_connect(self, params):
        """ Configure & launch the VPN client.

            Parameters:

              'kind'      : required
                  Indicates the kind of VPN which is to be used.
                  Valid values are:

                    l2tpipsec-cert
                    l2tpipsec-psk
                    openvpn

              'vpn-host-ip': optional
                  Specifies the IP of the VPN server.  If not provided,
                  defaults to 'self.server_wifi_ip'

              'files'      : required
                  A dict which contains a set of file names.

                     'ca-certificate'     : path to CA certificate file
                     'client-certificate' : path to client certificate file
                     'client-key'         : path to client key file

              'remote-cert-tls' : optional
                    If provided, this option can be 'server', 'client' or
                    'none'.
                    If not specified, the default is 'none'.
                    The value provided is passed directly to 'connect-vpn'.
        """
        self.vpn_client_kill({}) # Must be first.  Relies on self.vpn_kind.
        self.vpn_kind = params.get('kind', None)

        # Starting up the VPN client may cause the DUT's routing table (esp.
        # the default route) to change.  Set up a host route backwards so
        # we don't lose our control connection in that event.
        self.__add_host_route(self.client)

        if self.vpn_kind is None:
            raise error.TestFail('No VPN kind specified for this test.')
        elif self.vpn_kind == 'openvpn':
            # 'ca_certificate', 'client-certificate' and 'client-key'.
            vpn_host_ip            = params.get('vpn-host-ip',
                                                self.server_wifi_ip)
            cert_pathnames         = params.get('files', {})
            remote_cert_tls_option = ""
            remote_cert_tls        = params.get('remote-cert-tls', None)

            if remote_cert_tls is not None:
                remote_cert_tls_option = "--remote-cert-tls " + remote_cert_tls

            result = self.client.run('%s/test/connect-vpn '
                                     '--verbose '
                                     '%s '
                                     'openvpn vpn-name %s vpn-domain '
                                     '%s '   # ca certificate
                                     '%s '   # client certificate
                                     '%s' %  # client key
                                     (self.client_cmd_flimflam_lib,
                                      remote_cert_tls_option,
                                      vpn_host_ip,
                                      cert_pathnames['ca-certificate'],
                                      cert_pathnames['client-certificate'],
                                      cert_pathnames['client-key']))
        elif self.vpn_kind == 'l2tpipsec-psk':
            # vpn_host_ip is self.server.ip because that is the
            # adapter that ipsec listens on.
            vpn_host_ip = params.get('vpn-host-ip', self.server.ip)
            password    = params.get('password'  , None)
            chapuser    = params.get('chapuser'  , None)
            chapsecret  = params.get('chapsecret', None)
            result = self.client.run('%s/test/connect-vpn '
                                     '--verbose '
                                     'l2tpipsec-psk vpn-name %s vpn-domain '
                                     '%s '  # password
                                     '%s '  # chapuser
                                     '%s' % # chapsecret
                                     (self.client_cmd_flimflam_lib,
                                      vpn_host_ip,
                                      password, chapuser, chapsecret))
        elif self.vpn_kind == 'l2tpipsec-cert':
            # vpn_host_ip is self.server.ip because that is the
            # adapter that ipsec listens on.
            vpn_host_ip = params.get('vpn-host-ip', self.server.ip)
            chapuser    = params.get('chapuser'  , None)
            chapsecret  = params.get('chapsecret', None)
            ca_cert_id  = params.get('cacertid', None)

            result = self.client.run('%s/test/connect-vpn '
                                     '--verbose '
                                     'l2tpipsec-cert vpn-name %s vpn-domain '
                                     '%s '   # CACertNSS
                                     '0 '    # ClientCertSlot
                                     '%s '   # ClientCertID
                                     '%s '   # PIN
                                     '%s '   # chapuser
                                     '%s' %  # chapsecret
                                     (self.client_cmd_flimflam_lib,
                                      vpn_host_ip,
                                      ca_cert_id,
                                      site_eap_certs.cert_1_tpm_key_id,
                                      site_eap_certs.auth_pin,
                                      chapuser,
                                      chapsecret))
        else:
            raise error.TestFail('(internal error): No launch case '
                                 'for VPN kind (%s)' % self.vpn_kind)

    def vpn_client_kill(self, params):
        """ Kill the VPN client if it's running. """
        if self.vpn_kind is not None:
            if self.vpn_kind == 'openvpn':
                self.client.run("pkill openvpn")
            elif self.vpn_kind in ('l2tpipsec-psk', 'l2tpipsec-cert'):
                self.client.run("/usr/sbin/ipsec stop")
            else:
                raise error.TestFail('(internal error): No kill case '
                                     'for VPN kind (%s)' % self.vpn_kind)
            self.vpn_kind = None

        self.__del_host_route(self.client)


    def __add_host_route(self, host):
        # What is the local address we use to get to the test host?
        local_ip = site_host_route.LocalHostRoute(host.ip).route_info["src"]

        # How does the test host currently get to this local address?
        host_route = site_host_route.RemoteHostRoute(host, local_ip).route_info

        # Flatten the returned dict into a single string
        route_args = " ".join(" ".join(x) for x in host_route.iteritems())

        self.host_route_args[host.ip] = "%s %s" % (local_ip, route_args)
        host.run("ip route add %s" % self.host_route_args[host.ip])

    def __del_host_route(self, host):
        if host.ip in self.host_route_args:
            host.run("ip route del %s" % self.host_route_args.pop(host.ip))

    def host_route_cleanup(self, params):
        for host in (self.client, self.server, self.router):
            self.__del_host_route(host)

    def log_time_diff(self, params):
        log_file = self.client_logfile

        time_diff = self.install_script('site_log_time_diff.py')
        result = self.client.run("python '%s' --from='%s' --to='%s'" %
                                      (time_diff, params['from'], params['to']))

        if '-' in result.stdout:
            logging.info("Unable to find timespan")
            return

        if "perf" in params:
            self.write_perf({params['perf']:float(result.stdout)})

    def client_deauth(self, params):
        self.wifi.deauth({'client': self.client.wlan_mac})

    def client_reboot(self, params):
        self.client_installed_scripts = {}

        if 'timeout' not in params:
            logging.info("Using default reboot timeout")
            self.client.reboot()
        else:
            reboot_timeout = float(params['timeout'])
            logging.info("Reboot timeout is %f seconds", reboot_timeout)
            self.client.reboot(timeout=reboot_timeout)

        self.profile_cleanup()
        self.profile_create(self.test_profile)
        self.profile_push(self.test_profile)

    def __store_pkcs11_resource(self, pkcs11_lib, user_pin, slot_id,
                                label, der_file_path, resource_type):
        self.client.run('pkcs11-tool '
                        '--module=%s '
                        '--pin %s '
                        '--id %s '
                        '--label %s '
                        '--write-object %s '
                        '--type %s' %
                        (pkcs11_lib,
                         user_pin,
                         slot_id,
                         label,
                         der_file_path,
                         resource_type))

    def client_check_ipv6(self, params):
        addrs = self.__get_ip6addrs(self.client, self.client_wlanif)
        errors = []
        if 'address_count' in params:
            expected = int(params['address_count'])
            if expected != len(addrs):
                errors.append('IPv6 address count %d is different from '
                              'expected %d' % (len(addrs), expected))

        if 'local_count' in params:
            local_count = 0
            expected = int(params['local_count'])
            for addr in addrs:
                if addr.startswith('fe80'):
                    local_count += 1
            if local_count != expected:
                errors.append('IPv6 address local count %d is different from '
                              'expected %d' % (local_count, expected))

        if 'mac_count' in params:
            mac_count = 0
            expected = int(params['mac_count'])
            mac_parts = self.client.wlan_mac.split(':')
            # Convert last 3 octets of MAC into suffix of IPv6 address
            shorts = [int(mac_parts[-3], 16), int(''.join(mac_parts[-2:]), 16)]
            mac_suffix_re = re.compile('%x:%x/' % tuple(shorts))
            for addr in addrs:
                if mac_suffix_re.search(addr):
                    mac_count += 1
            if mac_count != expected:
                errors.append('IPv6 address mac count %d is different from '
                              'expected %d' % (mac_count, expected))

        if 'default_route' in params:
            result = self.client.run('%s -6 route show dev %s default' %
                                     (self.client_cmd_ip, self.client_wlanif))

            found = bool('default' in result.stdout)
            expected = bool(params['default_route'])
            if found != expected:
                errors.append('IPv6 default route found == %s '
                              'from expected %s' % (found, expected))


        if errors:
            errors.append('Addresses are: %s' % ', '.join(addrs))
            raise error.TestFail('\n'.join(errors))

    def client_start_statistics(self, params):
        """ Start capturing network statistics on the client """
        self.client_stop_statistics({})
        script = 'site_wlan_statistics.py'
        script_client_file = self.install_script(script)

        cmd = ('python %s --count=%s --period=%s' %
               (script_client_file,
                params.get('count', '-1'),
                params.get('period', '1')))
        logging.info(cmd)
        self.client_stats_thread = remote_command.Command(self.client, cmd)

    def client_stop_statistics(self, params):
        self.client.run('pkill -f site_wlan_statistics.py',
                        ignore_status=True)
        if self.client_stats_thread is not None:
            self.client_stats_thread.join()
            stats = self.client_stats_thread.result.stdout
            logging.info(stats)
            file(self.__get_local_file(
                    'client_interface_statistics_%02d.txt'), 'w').write(stats)
            self.client_stats_thread = None

    def client_test_ipaddr(self, params):
        interface = params.get('interface', self.client_wlanif)
        self.__get_ipaddr(self.client, interface)

    def client_configure_service(self, params):
        guid = params.pop('GUID', '')
        args = ''
        for var, val in params.iteritems():
            args += ' %s %s' % (var, val)
        self.client.run('%s/test/configure-service %s %s' %
                        (self.client_cmd_flimflam_lib, guid, args))

    def client_roam(self, params):
        instance = params.get('instance', 0)
        wifi_mac = self.wifi.get_hostapd_mac(instance)
        # The "wpa_cli" command can only be run as the "wpa" user.  That
        # user does not have a valid shell, so without specifying one, the
        # "su" command will fail.
        self.client.run('su wpa -s /bin/bash -c "%s roam %s"' %
                        (self.client_cmd_wpa_cli, wifi_mac))


def __byfile(a, b):
    if a['file'] < b['file']:
        return -1
    elif a['file'] > b['file']:
        return 1
    else:
        return 0


def read_tests(dir, *args):
    """
    Collect WiFi test tuples from files.  File names are used to
    sort the test objects so the convention is to name them NNN<test>
    where NNN is a decimal number used to sort and <test> is an
    identifying name for the test; e.g. 000Check11b
    """
    tests = []
    for file in os.listdir(dir):
        if any(fnmatch.fnmatch(file, pat) for pat in args):
            fd = open(os.path.join(dir, file))
            try:
                test = eval(fd.read())
            except Exception, e:
                logging.error("%s: %s", os.path.join(dir, file), str(e))
                raise e
            test['file'] = file
            tests.append(test)
    # use filenames to sort
    return sorted(tests, cmp=__byfile)


def read_wifi_testbed_config(file, client_addr=None, server_addr=None,
        router_addr=None):
    # read configuration file
    fd = open(file)
    config = eval(fd.read())

    # Read in attributes from host config database
    client_attributes = site_host_attributes.HostAttributes(client_addr)

    # client must be reachable on the control network
    client = config['client']
    if client_addr is not None:
        client['addr'] = client_addr

    # router must be reachable on the control network
    router = config['router']
    if router_addr is None and hasattr(client_attributes, 'router_addr'):
        router_addr = client_attributes.router_addr
    if router_addr is not None:
        router['addr'] = router_addr

    server = config['server']
    if server_addr is None and hasattr(client_attributes, 'server_addr'):
        server_addr = client_attributes.server_addr
    if server_addr is not None:
        server['addr'] = server_addr

    # tag jobs w/ the router's address on the control network
    config['tagname'] = router['addr']

    return config

def run_test_dir(test_name, job, args, machine):
    # convert autoserv args to something usable
    opts = dict([[k, v] for (k, e, v) in [x.partition('=') for x in args]])

    # config file located under third_party/autotest/files/client/config/
    config_file = opts.get('config_file', 'wifi_testbed_config')

    test_pat = opts.get('test_pat', '[0-9]*')
    if utils.host_is_in_lab_zone(machine):
        # If we are in the lab use the names for the server, AKA rspro,
        # and the router as defined in:
        # go/chromeos-lab-hostname-convention
        server_addr = wifi_test_utils.get_server_addr_in_lab(machine)
        router_addr = wifi_test_utils.get_router_addr_in_lab(machine)
    else:
        server_addr = opts.get('server_addr', None)
        router_addr = opts.get('router_addr', None)

    run_options = opts.get('run_options', '').split(',')

    config = read_wifi_testbed_config(
        os.path.join(job.configdir, config_file),
        client_addr = machine,    # NB: take client identity from command line
        router_addr = router_addr,
        server_addr = server_addr)
    server = config['server']
    router = config['router']
    attenuator = config.get('attenuator', dict())
    config['run_options'] = run_options

    logging.info("Client %s, Server %s, AP %s, Attenuator %s" % \
        (machine, server.get('addr', 'N/A'), router['addr'],
         attenuator.get('addr', 'N/A')))

    test_dir = os.path.join(job.serverdir, "site_tests", test_name)

    for t in read_tests(test_dir, test_pat):
       job.run_test(test_name, testcase=t, config=config, tag=t['file'])


class test(test.test):
  """
  Base class for network_WiFi* classes that are created in the control
  directory for each test suite
  """
  version = 1
  testtype = WiFiTest

  def expect_failure(self, name, reason):
    if reason is None:
      reason = "no reason given"
    logging.info("%s: ignore failure (%s)", name, reason)


  # The testcase config, setup, etc are done out side the individual
  # test loop, in the control file.
  def run_once(self, testcase, config):
    name = testcase['name']
    try:
      if 'skip_test' in testcase and 'no_skip' not in config['run_options']:
        logging.info("%s: SKIP: %s", name, testcase['skip_test'])
        raise error.TestNAError(testcase['skip_test'])
      else:
        wt = self.testtype(name, testcase['steps'],
                           testcase.get('requires', []), config)
        wt.run()
        wt.write_keyvals(self)
    except error.TestFail:
      if 'expect_failure' in testcase:
        self.expect_failure(name, testcase['expect_failure'])
      else:
        raise
    except Exception, e:
      if 'expect_failure' in testcase:
        self.expect_failure(name, testcase['expect_failure'])
      else:
        raise
