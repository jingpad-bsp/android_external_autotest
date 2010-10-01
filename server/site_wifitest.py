# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import common, fnmatch, logging, os, re, string, threading, time

from autotest_lib.server import autotest, hosts, subcommand
from autotest_lib.server import site_bsd_router
from autotest_lib.server import site_linux_router
from autotest_lib.server import site_host_attributes
from autotest_lib.server import site_eap_tls
from autotest_lib.server import test
from autotest_lib.client.common_lib import error

class NotImplemented(Exception):
    def __init__(self, what):
        self.what = what


    def __str__(self):
        return repr("Test method '%s' not implemented" % self.what)


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

    def __init__(self, name, steps, config):
        self.name = name
        self.steps = steps
        self.perf_keyvals = {}

        router = config['router']
        self.router = hosts.create_host(router['addr'])
        # NB: truncate SSID to 32 characters
        self.defssid = self.__get_defssid(router['addr'])[0:32]

        defaults = config.get('defaults', {})
        self.deftimeout = defaults.get('timeout', 30)
        self.defpingcount = defaults.get('pingcount', 10)
        self.defwaittime = str(defaults.get('netperf_wait_time', 3))
        if 'type' not in router:
            # auto-detect router type
            if site_linux_router.isLinuxRouter(self.router):
                router['type'] = 'linux'
            elif site_bsd_router.isBSDRouter(self.router):
                router['type'] = 'bsd'
            else:
                 raise error.TestFail('Unable to autodetect router type')
        if router['type'] == 'linux':
            self.wifi = site_linux_router.LinuxRouter(self.router, router,
                self.defssid)
        elif router['type'] == 'bsd':
            self.wifi = site_bsd_router.BSDRouter(self.router, router,
                self.defssid)
        else:
            raise error.TestFail('Unsupported router')

        #
        # The client machine must be reachable from the control machine.
        # The address on the wifi network is retrieved each time it
        # associates to the router.
        #
        client = config['client']
        self.client = hosts.create_host(client['addr'])
        self.client_at = autotest.Autotest(self.client)
        self.client_wifi_ip = None       # client's IP address on wifi net
        # interface name on client
        self.client_wlanif = client.get('wlandev', "wlan0")

        #
        # The server machine may be multi-homed or only on the wifi
        # network.  When only on the wifi net we suppress server_*
        # requests since we cannot initiate them from the control machine.
        #
        server = config['server']
        # NB: server may not be reachable on the control network
        if 'addr' in server:
            self.server = hosts.create_host(server['addr'])
            self.server_at = autotest.Autotest(self.server)
            # if not specified assume the same as the control address
            self.server_wifi_ip = server.get('wifi_addr', self.server.ip)
            self.__server_discover_commands(server)
        else:
            self.server = None;
            # NB: wifi address must be set if not reachable from control
            self.server_wifi_ip = server['wifi_addr']

        # potential bg thread for ping untilstop
        self.ping_thread = None

        # potential bg thread for client network monitoring
        self.client_netdump_thread = None
        self.__client_discover_commands(client)
        self.firewall_rules = []

        # Find all repeated steps and create iterators for them
        self.iterated_steps = {}
        step_names = [step[0] for step in steps]
        for step_name in list(set(step_names)):
            if step_names.count(step_name) > 1:
                self.iterated_steps[step_name] = 0

    def cleanup(self, params):
        """ Cleanup state: disconnect client and destroy ap """
        self.disconnect({})
        self.wifi.destroy({})
        self.client_netdump_stop({})
        self.firewall_cleanup({})


    def __client_discover_commands(self, client):
        self.client_cmd_netdump = client.get('cmd_netdump', 'tshark')
        self.client_cmd_ifconfig = client.get('cmd_ifconfig', 'ifconfig')
        self.client_cmd_iw = client.get('cmd_iw', 'iw')
        self.client_cmd_netperf = client.get('cmd_netperf_client',
                                             '/usr/local/bin/netperf')
        self.client_cmd_netserv = client.get('cmd_netperf_server',
                                             '/usr/local/sbin/netserver')
        self.client_cmd_iptables = '/sbin/iptables'


    def __server_discover_commands(self, server):
        self.server_cmd_netperf = server.get('cmd_netperf_client',
                                             '/usr/bin/netperf')
        self.server_cmd_netserv = server.get('cmd_netperf_server',
                                             '/usr/bin/netserver')
        # /usr/bin/ping is preferred, as it is likely to be iputils
        if self.__is_installed(self.server, '/usr/bin/ping'):
            self.server_ping_cmd = '/usr/bin/ping'
        else:
            self.server_ping_cmd = 'ping'


    def __get_defssid(self, ipaddr):
        #
        # Calculate ssid based on test name; this lets us track progress
        # by watching beacon frames.
        #
        return re.sub('[^a-zA-Z0-9_]', '_', "%s_%s" % (self.name, ipaddr))


    def run(self):
        """
        Run a WiFi test.  Each step is interpreted as a method either
        in this class or the ancillary router class and invoked with
        the supplied parameter dictionary.  If the method is prefixed
        with '!' then we expect the operation to fail; this is useful,
        for example, for testing parameter checking in flimflam.
        """
        for s in self.steps:
            method = s[0]
            if method[0] == '!':
                expect_failure = True
                method = method[1:]
            else:
                expect_failure = False
            if len(s) > 1:
                params = s[1]
            else:
                params = {}

            # What should perf data be prefixed with?
            if 'perf_prefix' in params:
                self.prefix = '%s_%s' % (method, params.pop('perf_prefix'))
            elif method in self.iterated_steps:
                self.prefix = '%s_%d' % (method, self.iterated_steps[method])
                self.iterated_steps[method] += 1
            else:
                self.prefix = method

            if expect_failure is True:
                logging.info("%s: step '%s' (expect failure)  params %s",
                    self.name, method, params)
            else:
                logging.info("%s: step '%s' params %s", self.name, method,
                    params)

            func = getattr(self, method, None)
            if func is None:
                func = getattr(self.wifi, method, None)
            if func is not None:
                try:
                    func(params)
                    if expect_failure is True:
                        raise error.TestFail("Expected failure")
                except Exception, e:
                    if expect_failure is True:
                        continue
                    logging.error("%s: Step '%s' failed: %s; abort test",
                        self.name, method, str(e))
                    self.cleanup(params)
                    raise e
            else:
                logging.error("%s: Step '%s' unknown; abort test",
                    self.name, method)
                self.cleanup(params)
                break

        # Other cleanup steps might be optional, but this is mandatory
        self.client_netdump_stop({})


    def write_keyvals(self, job):
        job.write_perf_keyval(self.perf_keyvals)

    def write_perf(self, data):
        for key, value in data.iteritems():
            self.perf_keyvals['%s_%s' % (self.prefix, key)] = value

    def __get_ipaddr(self, host, ifnet):
        # XXX gotta be a better way to do this
        result = host.run("%s %s" % (self.client_cmd_ifconfig, ifnet))
        m = re.search('inet addr:([^ ]*)', result.stdout)
        if m is None:
             raise error.TestFail("No inet address found")
        return m.group(1)


    def install_script(self, script_name, *support_scripts):
        script_client_dir = self.client.get_tmp_dir()
        script_client_file = os.path.join(script_client_dir, script_name)
        for copy_file in [script_name] + list(support_scripts):
            src_file = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                    copy_file)
            dest_file = os.path.join(script_client_dir,
                                     os.path.basename(src_file))
            self.client.send_file(src_file, dest_file, delete_dest=True)
        return script_client_file


    def connect(self, params):
        """ Connect client to AP/router """

        script_client_file = self.install_script('site_wlan_connect.py')
        if 'eap-tls' in params:
            params.update(site_eap_tls.client_config(self.client,
                                                     params['eap-tls']))

        result = self.client.run('python "%s" "%s" "%s" "%s" "%d" "%d"' %
            (script_client_file,
            params.get('ssid', self.wifi.get_ssid()),
            params.get('security', ''),
            params.get('psk', ''),
            params.get('assoc_timeout', self.deftimeout),
            params.get('config_timeout', self.deftimeout))).stdout.rstrip()

        result_times = re.match("OK ([0-9\.]*) ([0-9\.]*) .*", result)

        self.write_perf({'config_s': result_times.group(1),
                          'assoc_s': result_times.group(2)})
        for k in ('already_connected', 'clear_error', 'fast_fail',
                  'get_prop', 'in_progress', 'lost_dbus', 'multiple_attempts'):
            if re.search(k, result) is not None:
                self.write_perf({k:'true'})

        print "%s: %s" % (self.name, result)

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

        script_client_file = self.install_script('site_wlan_disconnect.py')
        result = self.client.run('python "%s" "%s" "%d"' %
            (script_client_file,
            params.get('ssid', self.defssid),
            params.get('wait_timeout', self.deftimeout))).stdout.rstrip()

        print "%s: %s" % (self.name, result)


    def __wait_service_start(self, params):
        """ Wait for service transitions on client. """

        script_client_file = self.install_script('site_wlan_wait_state.py')
        args = []

        # Whether to print out all state transitions of watched services to
        # stderr
        if params.get('debug', False):
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


    def __wait_service_complete(self, result):
        print "%s: %s" % (self.name, result)

        states = self.wait_service_states
        counts = {}
        for service, state in states:
            cstate = state.strip('+')
            if state in counts:
                counts[cstate] = 1
            else:
                counts[cstate] = 0

        for (service, state), intr in zip(states, result.stdout.split(' ')):
            if intr.startswith('ERR_'):
                raise error.TestFail('Wait for step %s failed with error %s' % 
                                     (state, intr))
            cstate = state.strip('+')
            if counts[cstate]:
                index = '%s%d' % (cstate, counts[cstate] - 1)
                counts[cstate] += 1
            else:
                index = cstate

            self.write_perf({ index:float(intr) })
            print "  %s: %s" % (state, intr)


    def wait_service(self, params):
        result = self.client.run(self.__wait_service_start(params))
        self.__wait_service_complete(result)


    def wait_service_suspend_bg(self, params):
        params['after_command'] = self.__wait_service_start(params)
        self.client_suspend_bg(params)


    def wait_service_suspend_end(self, params):
        self.client_suspend_end(params)
        self.__wait_service_complete(self.client_suspend_thread.result)


    def client_powersave_on(self, params):
        """ Enable power save operation """
        self.client.run("iw dev %s set power_save on" % self.client_wlanif)


    def client_powersave_off(self, params):
        """ Disable power save operation """
        self.client.run("iw dev %s set power_save off" % self.client_wlanif)


    def __client_check(self, param, want):
        """ Verify negotiated station mode parameter """
        result = self.client.run("cat '%s/%s'" %
            (self.client_debugfs_path, param))
        got = result.stdout.rstrip()       # NB: chop \n
        if got != want:
            raise error.TestFail("client_check_%s: wanted %s got %s",
                param, want, got)


    def client_check_bintval(self, params):
        """ Verify negotiated beacon interval """
        self.__client_check("beacon_int", params[0])


    def client_check_dtimperiod(self, params):
        """ Verify negotiated DTIM period """
        self.__client_check("dtim_period", params[0])


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
        raise NotImplemented("client_monitor_start")


    def client_monitor_stop(self, params):
        """ Stop monitoring system events """
        raise NotImplemented("client_monitor_stop")


    def client_check_event_mic(self, params):
        """ Check for MIC error event """
        raise NotImplemented("client_check_event_mic")


    def client_check_event_countermeasures(self, params):
        """ Check for WPA CounterMeasures event """
        raise NotImplemented("client_check_event_countermeasures")


    def sleep(self, params):
        time.sleep(float(params['time']))


    def __unreachable(self, method):
        logging.info("%s: SKIP step %s; server is unreachable",
            self.name, method)


    def __ping_args(self, params):
        args = ""
        if 'count' in params:
            args += " -c %s" % params['count']
        if 'size' in params:
            args += " -s %s" % params['size']
        if 'bcast' in params:
            args += " -b"
        if 'flood' in params:
            args += " -f"
        if 'interval' in params:
            args += " -i %s" % params['interval']
        if 'qos' in params:
            ac = string.lower(params['qos'])
            if ac == 'be':
                args += " -Q 0x04"
            elif ac == 'bk':
                args += " -Q 0x02"
            elif ac == 'vi':
                args += " -Q 0x08"
            elif ac == 'vo':
                args += " -Q 0x10"
            else:
                args += " -Q %s" % ac
        return args


    def __get_pingstats(self, str):
        stats = {}
        for k in ('xmit', 'recv', 'loss', 'min', 'avg', 'max'):
            stats[k] = '???'
        m = re.search('([0-9]*) packets transmitted,[ ]*([0-9]*)[ ]'
            '(packets |)received, ([0-9]*)', str)
        if m is not None:
            stats['xmit'] = m.group(1)
            stats['recv'] = m.group(2)
            stats['loss'] = m.group(4)
        m = re.search('(round-trip|rtt) min[^=]*= '
                      '([0-9.]*)/([0-9.]*)/([0-9.]*)', str)
        if m is not None:
            stats['min'] = m.group(2)
            stats['avg'] = m.group(3)
            stats['max'] = m.group(4)
        return stats


    def __print_pingstats(self, label, stats):
        logging.info("%s: %s%s/%s, %s%% loss, rtt %s/%s/%s",
            self.name, label, stats['xmit'], stats['recv'], stats['loss'],
             stats['min'], stats['avg'], stats['max'])


    def client_ping(self, params):
        """ Ping the server from the client """
        ping_ip = params.get('ping_ip', self.server_wifi_ip)
        count = params.get('count', self.defpingcount)
        # set timeout for 3s / ping packet
        result = self.client.run("ping %s %s" % \
            (self.__ping_args(params), ping_ip), timeout=3*int(count))

        stats = self.__get_pingstats(result.stdout)
        self.write_perf(stats)
        self.__print_pingstats("client_ping ", stats)


    def client_ping_bg(self, params):
        """ Ping the server from the client """
        ping_ip = params.get('ping_ip', self.server_wifi_ip)
        cmd = "ping %s %s" % (self.__ping_args(params), ping_ip)
        self.ping_thread = HelperThread(self.client, cmd)
        self.ping_thread.start()


    def client_ping_bg_stop(self, params):
        if self.ping_thread is not None:
            self.client.run("pkill ping")
            self.ping_thread.join()
            self.ping_thread = None


    def server_ping(self, params):
        """ Ping the client from the server """
        if self.server is None:
            self.__unreachable("server_ping")
            return
        ping_ip = params.get('ping_ip', self.client_wifi_ip)
        count = params.get('count', self.defpingcount)
        # set timeout for 3s / ping packet
        result = self.server.run("%s %s %s" % \
            (self.server_ping_cmd, self.__ping_args(params),
             ping_ip), timeout=3*int(count))

        stats = self.__get_pingstats(result.stdout)
        self.write_perf(stats)
        self.__print_pingstats("server_ping ", stats)


    def server_ping_bg(self, params):
        """ Ping the client from the server """
        if self.server is None:
            self.__unreachable("server_ping_bg")
            return
        ping_ip = params.get('ping_ip', self.client_wifi_ip)
        cmd = "ping %s %s" % (self.__ping_args(params), ping_ip)
        self.ping_thread = HelperThread(self.server, cmd)
        self.ping_thread.start()


    def server_ping_bg_stop(self, params):
        if self.server is None:
            self.__unreachable("server_ping_bg_stop")
            return
        if self.ping_thread is not None:
            self.server.run("pkill ping")
            self.ping_thread.join()
            self.ping_thread = None


    def __run_iperf(self, client_ip, server_ip, params):
        template = ''.join(["job.run_test('iperf', \
            server_ip='%s', client_ip='%s', role='%s'"])
        if 'udp' in params:
            template += ", udp=True"
        if 'bidir' in params:
            template += ", bidirectional=True"
        if 'time' in params:
            template += ", test_time=%s" % params['time']

        # add a tag to distinguish runs when multiple tests are run
        if 'tag' in params:
            tag = params['tag']
        elif 'udp' in params:
            tag = "udp"
        else:
            tag = "tcp"
        if 'bidir' in params:
            tag += "_bidir"
        template += ", tag='%s'" % tag

        template += ")"

        client_control_file = template % (server_ip, client_ip, 'client')
        client_command = subcommand.subcommand(self.client_at.run,
               [client_control_file, self.client.hostname])
        cmds = [client_command]

        if self.server is None:
            logging.info("%s: iperf %s => (%s)",
                self.name, client_ip, server_ip)
        else:
            server_control_file = template % (server_ip, client_ip, 'server')
            server_command = subcommand.subcommand(self.server_at.run,
                   [server_control_file, self.server.hostname])
            cmds.append(server_command)

            logging.info("%s: iperf %s => %s", self.name, client_ip, server_ip)

        subcommand.parallel(cmds)


    def client_iperf(self, params):
        """ Run iperf on the client against the server """
        self.__run_iperf(self.client_wifi_ip, self.server_wifi_ip, params)


    def server_iperf(self, params):
        """ Run iperf on the server against the client """
        if self.server is None:
            self.__unreachable("server_iperf")
            return
        self.__run_iperf(self.server_wifi_ip, self.client_wifi_ip, params)


    def __is_installed(self, host, filename):
        result = host.run("ls %s" % filename, ignore_status=True)
        m = re.search(filename, result.stdout)
        return m is not None


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
            client = { 'host': self.server, 'cmd': self.server_cmd_netperf,
                       'target': self.client_wifi_ip }

            # Open up access from the server into our DUT
            np_rules.append(self.__firewall_open('tcp', self.server_wifi_ip))
            np_rules.append(self.__firewall_open('udp', self.server_wifi_ip))
        else:
            server = { 'host': self.server, 'cmd': self.server_cmd_netserv }
            client = { 'host': self.client, 'cmd': self.client_cmd_netperf,
                       'target': self.server_wifi_ip }

        # If appropriate apps are not installed, raise an error
        if not self.__is_installed(client['host'], client['cmd']) or \
                not self.__is_installed(server['host'], server['cmd']):
            raise error.TestFail('Unable to find netperf on client or server')

        # There are legitimate ways this command can fail, eg. already running
        server['host'].run(server['cmd'], ignore_status=True)

        # Assemble arguments for client command
        test = params.get('test', 'TCP_STREAM')
        netperf_args = '-H %s -t %s -l %d' % (client['target'], test,
                                              params.get('test_time', 15))

        # Run netperf command and receive command results
        t0 = time.time()
        results = client['host'].run("%s %s" % (client['cmd'], netperf_args))
        actual_time = time.time() - t0
        logging.info('actual_time: %f', actual_time)

        # Close up whatever firewall rules we created for netperf
        for rule in np_rules:
            self.__firewall_close(rule)

        self.write_perf({'test':test, 'mode':mode, 'actual_time':actual_time})

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
            self.write_perf({'Trasnfer_Rate':float(lines[6].split()[5])})
        else:
            raise error.TestError('Unhandled test')

        return True


    def client_netperf(self, params):
        """ Run netperf on the client against the server """
        self.__run_netperf('client', params)


    def server_netperf(self, params):
        """ Run netperf on the server against the client """
        if self.server is None:
            self.__unreachable("server_netperf")
            return
        self.__run_netperf('server', params)


    def __create_netdump_dev(self, devname='mon0'):
        self.client.run("%s dev %s del || /bin/true" % (self.client_cmd_iw,
                                                        devname))
        self.client.run("%s dev %s interface add %s type monitor" %
                        (self.client_cmd_iw, self.client_wlanif, devname))
        self.client.run("%s %s up" % (self.client_cmd_ifconfig, devname))
        return devname


    def __destroy_netdump_dev(self, devname='mon0'):
        self.client.run("%s dev %s del" % (self.client_cmd_iw, devname))


    def client_netdump_start(self, params):
        """ Ping the server from the client """
        self.client.run("pkill %s || /bin/true" % self.client_cmd_netdump)
        devname = self.__create_netdump_dev()
        self.client_netdump_dir = self.client.get_tmp_dir()
        self.client_netdump_file = os.path.join(self.client_netdump_dir,
                                                "client_netdump.cap")
        cmd = "%s -i %s -w %s" % (self.client_cmd_netdump, devname,
                                  self.client_netdump_file)
        logging.info(cmd)
        self.client_netdump_thread = HelperThread(self.client, cmd)
        self.client_netdump_thread.start()


    def client_netdump_stop(self, params):
        if self.client_netdump_thread is not None:
            self.__destroy_netdump_dev()
            self.client.run("pkill %s" % self.client_cmd_netdump)
            self.client.get_file(self.client_netdump_file, '.')
            self.client.delete_tmp_dir(self.client_netdump_dir)
            self.client_netdump_thread.join()
            self.client_netdump_thread = None


    def client_suspend(self, params):
        """ Suspend the system """

        script_client_file = self.install_script('site_system_suspend.py',
                                                 '../client/common_lib/rtc.py',
                                                 '../client/common_lib/'
                                                 'sys_power.py')
        result = self.client.run('python "%s" %d' %
            (script_client_file, int(params.get("suspend_time", 5))))


    def client_suspend_bg(self, params):
        """ Suspend the system in the background """

        script_client_file = self.install_script('site_system_suspend.py',
                                                 '../client/common_lib/rtc.py',
                                                 '../client/common_lib/'
                                                 'sys_power.py')
        cmd = ('python "%s" %d %s' %
               (script_client_file,
                int(params.get("suspend_time", 5)),
                params.get("after_command", '')))
        self.client_suspend_thread = HelperThread(self.client, cmd)
        self.client_suspend_thread.start()


    def client_suspend_end(self, params):
        """ Join the backgrounded suspend thread """

        self.client_suspend_thread.join()
        if self.client_suspend_thread.result.exit_status:
            raise error.TestError('suspend failed')

class HelperThread(threading.Thread):
    # Class that wraps a ping command in a thread so it can run in the bg.
    def __init__(self, client, cmd):
        threading.Thread.__init__(self)
        self.client = client
        self.cmd = cmd

    def run(self):
        # NB: set ignore_status as we're always terminated w/ pkill
        self.result = self.client.run(self.cmd, ignore_status=True)

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
            fd = open(os.path.join(dir, file));
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
        client['addr'] = client_addr;

    # router must be reachable on the control network
    router = config['router']
    if router_addr is None and hasattr(client_attributes, 'router_addr'):
        router_addr = client_attributes.router_addr
    if router_addr is not None:
        router['addr'] = router_addr;

    server = config['server']
    if server_addr is None and hasattr(client_attributes, 'server_addr'):
        server_addr = client_attributes.server_addr
    if server_addr is not None:
        server['addr'] = server_addr;
    # TODO(sleffler) check for wifi_addr when no control address

    # tag jobs w/ the router's address on the control network
    config['tagname'] = router['addr']

    return config

def run_test_dir(test_name, job, args, machines):
    # convert autoserv args to something usable
    opts = dict([[k, v] for (k, e, v) in [x.partition('=') for x in args]])

    config_file = opts.get('config_file', 'wifi_testbed_config')
    test_pat = opts.get('test_pat', '[0-9]*')
    router_addr = opts.get('router_addr', None)
    server_addr = opts.get('server_addr', None)

    config = read_wifi_testbed_config(
        os.path.join(job.configdir, config_file),
        client_addr = machines[0],    # NB: take client identity from command line
        router_addr = router_addr,
        server_addr = server_addr)
    server = config['server']
    router = config['router']

    logging.info("Client %s, Server %s, AP %s" % \
        (machines[0], server.get('addr', 'N/A'), router['addr']))

    test_dir = os.path.join(job.serverdir, "site_tests", test_name)

    for t in read_tests(test_dir, test_pat):
       job.run_test(test_name, testcase=t, config=config, tag=t['file'])

class test(test.test):
  """
  Base class for network_WiFi* classes that are created in the control
  directory for each test suite
  """
  version = 1

  def expect_failure(self, name, reason):
    if reason is None:
      reason = "no reason given"
    logging.info("%s: ignore failure (%s)", name, reason)


  # The testcase config, setup, etc are done out side the individual
  # test loop, in the control file.
  def run_once(self, testcase, config):
    name = testcase['name']
    try:
      if 'skip_test' in testcase:
        logging.info("%s: SKIP: %s", name, testcase['skip_test'])
      else:
        wt = WiFiTest(name, testcase['steps'], config)
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
        raise error.TestFail(e)
