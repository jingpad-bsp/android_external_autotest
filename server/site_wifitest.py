# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import common, fnmatch, logging, os, re, string, threading, time

from autotest_lib.server import autotest, subcommand
from autotest_lib.server import site_bsd_router
#from autotest_lib.server import site_linux_router

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

    def __init__(self, name, steps, router, client, server):
        self.name = name
        self.steps = steps
        self.router = router['host']
        #
        # The client machine must be reachable from the control machine.
        # The address on the wifi network is retrieved after it each time
        # it associates to the router.
        #
        self.client = client['host']
        self.client_at = autotest.Autotest(self.client)
        self.client_wifi_ip = None       # client's IP address on wifi net
        #
        # The server machine may be multi-homed or only on the wifi
        # network.  When only on the wifi net we suppress server_*
        # requests since we cannot initiate them from the control machine.
        #
        self.server = getattr(server, 'host', None)
        if self.server is not None:
            self.server_at = autotest.Autotest(self.server)
            # if not specified assume the same as the control address
            self.server_wifi_ip = getattr(server, 'wifi_addr', self.server.ip)
        else:
            # NB: must be set if not reachable from control
            self.server_wifi_ip = server['wifi_addr']

        # NB: truncate SSID to 32 characters
        self.defssid = self.__get_defssid()[0:32]
        # interface name on client
        self.wlanif = "wlan0"

        # XXX auto-detect router type
        self.wifi = site_bsd_router.BSDRouter(self.router, router, self.defssid)

        # potential bg thread for ping untilstop
        self.ping_thread = None


    def cleanup(self, params):
        """ Cleanup state: disconnect client and destroy ap """
        self.disconnect({})
        self.wifi.destroy({})


    def __get_defssid(self):
        #
        # Calculate ssid based on test name; this lets us track progress
        # by watching beacon frames.
        #
        return re.sub('[^a-zA-Z0-9_]', '_', \
            "%s_%s" % (self.name, self.router.ip))


    def run(self):
        """
        Run a WiFi test.  Each step is interpreted as a method either
        in this class or the ancillary router class and invoked with
        the supplied parameter dictionary.
        """
        for s in self.steps:
            method = s[0]
            if len(s) > 1:
                params = s[1]
            else:
                params = {}

            logging.info("%s: step '%s' params %s", self.name, method, params)

            func = getattr(self, method, None)
            if func is None:
                func = getattr(self.wifi, method, None)
            if func is not None:
                try:
                    func(params)
                except Exception, e:
                    logging.error("%s: Step '%s' failed: %s; abort test",
                        self.name, method, str(e))
                    self.cleanup(params)
                    break
            else:
                logging.error("%s: Step '%s' unknown; abort test",
                    self.name, method)
                self.cleanup(params)
                break


    def __get_connect_script(self, params):
        return '''
import dbus, dbus.mainloop.glib, gobject, logging, re, sys, time

ssid = "''' + params['ssid'] + '''"
security = "''' + params['security'] + '''"
psk = "''' + params.get('psk', "") + '''"
assoc_timeout = ''' + params.get('assoc_timeout', "15") + '''
config_timeout = ''' + params.get('config_timeout', "15") + '''

bus_loop = dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus(mainloop=bus_loop)
manager = dbus.Interface(bus.get_object("org.moblin.connman", "/"),
    "org.moblin.connman.Manager")

try:
    path = manager.GetService(({
        "Type": "wifi",
        "Mode": "managed",
        "SSID": ssid,
        "Security": security,
        "Passphrase": psk }))
    service = dbus.Interface(
        bus.get_object("org.moblin.connman", path),
        "org.moblin.connman.Service")
except Exception, e:
    print "FAIL(GetService): ssid %s exception %s" %(ssid, e)
    sys.exit(1)

try:
    service.Connect()
except Exception, e:
    print "FAIL(Connect): ssid %s exception %s" %(ssid, e)
    sys.exit(2)

status = ""
assoc_time = 0
# wait up to assoc_timeout seconds to associate
while assoc_time < assoc_timeout:
    properties = service.GetProperties()
    status = properties.get("State", None)
#    print>>sys.stderr, "time %3.1f state %s" % (assoc_time, status)
    if status == "failure":
        print "FAIL(assoc): ssid %s assoc %3.1f secs props %s" \\
        %(ssid, assoc_time, properties)
        sys.exit(3)
    if status == "configuration" or status == "ready":
        break
    time.sleep(.5)
    assoc_time += .5
if assoc_time >= assoc_timeout:
    print "TIMEOUT(assoc): ssid %s assoc %3.1f secs" %(ssid, assoc_time)
    sys.exit(4)

# wait another config_timeout seconds to get an ip address
config_time = 0
if status != "ready":
    while config_time < config_timeout:
        properties = service.GetProperties()
        status = properties.get("State", None)
#        print>>sys.stderr, "time %3.1f state %s" % (config_time, status)
        if status == "failure":
            print "FAIL(config): ssid %s assoc %3.1f config %3.1f secs" \\
                %(ssid, assoc_time, config_time)
            sys.exit(5)
        if status == "ready":
            break
        time.sleep(.5)
        config_time += .5
    if config_time >= config_timeout:
        print "TIMEOUT(config): ssid %s assoc %3.1f config %3.1f secs" \\
            %(ssid, assoc_time, config_time)
        sys.exit(6)
print "assoc %3.1f secs config %3.1f secs" % (assoc_time, config_time)
sys.exit(0)'''


    def __get_ipaddr(self, host, ifnet):
        # XXX gotta be a better way to do this
        result = host.run("ifconfig %s" % ifnet)
        m = re.search('inet addr:([^ ]*)', result.stdout)
        if m is None:
            raise Except, "No inet address found"
        return m.group(1)


    def connect(self, params):
        """ Connect client to AP/router """
        if 'ssid' not in params:
            params['ssid'] = self.defssid
        script = self.__get_connect_script(params)
        result = self.client.run("python<<'EOF'\n%s\nEOF\n" % script)
        print "%s: %s" % (self.name, result.stdout[0:-1])

        # fetch IP address of wireless device
        self.client_wifi_ip = self.__get_ipaddr(self.client, self.wlanif)
        logging.info("%s: client WiFi-IP is %s", self.name, self.client_wifi_ip)


    def __get_disconnect_script(self, params):
        return '''
import dbus, dbus.mainloop.glib, gobject, sys, time

ssid = "''' + params['ssid'] + '''"
wait_timeout = ''' + params.get('wait_timeout', "15") + '''

bus_loop = dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus(mainloop=bus_loop)
manager = dbus.Interface(bus.get_object("org.moblin.connman", "/"),
    "org.moblin.connman.Manager")

mprops = manager.GetProperties()
for path in mprops["Services"]:
    service = dbus.Interface(bus.get_object("org.moblin.connman", path),
        "org.moblin.connman.Service")
    sprops = service.GetProperties()
    if sprops.get("Name", None) != ssid:
        continue
    wait_time = 0
    try:
        service.Disconnect()
        while wait_time < wait_timeout:
            sprops = service.GetProperties()
            state = sprops.get("State", None)
#           print>>sys.stderr, "time %3.1f state %s" % (wait_time, state)
            if state == "idle":
                break
            time.sleep(.5)
            wait_time += .5
    except:
        pass
    print "disconnect in %3.1f secs" % wait_time
    break
sys.exit(0)'''


    def disconnect(self, params):
        """ Disconnect previously connected client """
        if 'ssid' not in params:
            params['ssid'] = self.defssid
        self.client_ping_bg_stop({})
        script = self.__get_disconnect_script(params)
        result = self.client.run("python<<'EOF'\n%s\nEOF\n" % script)
        print "%s: %s" % (self.name, result.stdout[0:-1])


    def client_check_bintval(self, params):
        """ Verify negotiated beacon interval """
        result = self.router.run("ifconfig %s" % self.wlanif)
        want = params[0]
        m = re.search('bintval ([0-9]*)', result.stdout)
        if m is None:
            raise NameError
        if m.group(1) != want:
            logging.error("client_check_bintval: wanted %s got %s",
                want, m.group(1))
            raise AssertionError


    def client_check_dtimperiod(self, params):
        """ Verify negotiated DTIM period """
        result = self.router.run("ifconfig %s" % self.wlanif)
        want = params[0]
        m = re.search('dtimperiod ([0-9]*)', result.stdout)
        if m is None:
            raise NameError
        if m.group(1) != want:
            logging.error("client_check_dtimperiod: wanted %s got %s",
                want, m.group(1))
            raise AssertionError


    def client_check_rifs(self, params):
        """ Verify negotiated RIFS setting """
        result = self.router.run("ifconfig %s" % self.wlanif)
        m = re.search('[^-]rifs', result.stdout)
        if m is None:
            raise AssertionError


    def client_check_shortgi(self, params):
        """ Verify negotiated Short GI setting """
        result = self.router.run("ifconfig %s" % self.wlanif)
        m = re.search('[^-]shortgi', result.stdout)
        if m is None:
            raise AssertionError


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
        m = re.search('([0-9]*) packets transmitted,[ ]*([0-9]*)[ ]'
            'received, ([0-9]*)', str)
        if m is not None:
            stats['xmit'] = m.group(1)
            stats['recv'] = m.group(2)
            stats['loss'] = m.group(3)
        m = re.search('rtt min[^=]*= ([0-9.]*)/([0-9.]*)/([0-9.]*)', str)
        if m is not None:
            stats['min'] = m.group(1)
            stats['avg'] = m.group(2)
            stats['max'] = m.group(3)
        return stats


    def __print_pingstats(self, label, stats):
        logging.info("%s: %s%s/%s, %s%% loss, rtt %s/%s/%s",
            self.name, label, stats['xmit'], stats['recv'], stats['loss'],
             stats['min'], stats['avg'], stats['max'])


    def client_ping(self, params):
        """ Ping the server from the client """
        ping_ip = params.get('ping_ip', self.server_wifi_ip)
        count = params.get('count', 10)
        # set timeout for 3s / ping packet
        result = self.client.run("ping %s %s" % \
            (self.__ping_args(params), ping_ip), timeout=3*int(count))

        self.__print_pingstats("client_ping ",
            self.__get_pingstats(result.stdout))


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
        count = params.get('count', 10)
        # set timeout for 3s / ping packet
        result = self.server.run("ping %s %s" % \
            (self.__ping_args(params), ping_ip), timeout=3*int(count))

        self.__print_pingstats("server_ping ",
            self.__get_pingstats(result.stdout))


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


    def __run_netperf(self, client_ip, server_ip, params):
        template = "job.run_test('"
        if self.server is None:
            template += "network_netperf2"
        else:
            template += "netperf2"
        template += "', server_ip='%s', client_ip='%s', role='%s'"
        if 'test' in params:
            template += ", test='%s'" % params['test']
        if 'bidir' in params:
            template += ", bidi=True"
        if 'time' in params:
            template += ", test_time=%s" % params['time']

        # add a tag to distinguish runs when multiple tests are run
        if 'tag' in params:
            template += ", tag='%s'" % params['tag']
        elif 'test' in params:
            template += ", tag='%s'" % params['test']

        template += ")"

        client_control_file = template % (server_ip, client_ip, 'client')
        client_command = subcommand.subcommand(self.client_at.run,
               [client_control_file, self.client.hostname])
        cmds = [client_command]

        if self.server is None:
            logging.info("%s: netperf %s => (%s)",
                self.name, client_ip, server_ip)
        else:
            server_control_file = template % (server_ip, client_ip, 'server')
            server_command = subcommand.subcommand(self.server_at.run,
                   [server_control_file, self.server.hostname])
            cmds.append(server_command)

            logging.info("%s: netperf %s => %s",
                self.name, client_ip, server_ip)

        subcommand.parallel(cmds)


    def client_netperf(self, params):
        """ Run netperf on the client against the server """
        self.__run_netperf(self.client_wifi_ip, self.server_wifi_ip, params)

    def server_netperf(self, params):
        """ Run netperf on the server against the client """
        if self.server is None:
            self.__unreachable("server_netperf")
            return
        self.__run_netperf(self.server_wifi_ip, self.client_wifi_ip, params)


class HelperThread(threading.Thread):
    # Class that wraps a ping command in a thread so it can run in the bg.
    def __init__(self, client, cmd):
        threading.Thread.__init__(self)
        self.client = client
        self.cmd = cmd

    def run(self):
        # NB: set ignore_status as we're always terminated w/ pkill
        self.client.run(self.cmd, ignore_status=True)


def __byfile(a, b):
    if a['file'] < b['file']:
        return -1
    elif a['file'] > b['file']:
        return 1
    else:
        return 0

def read_tests(dir, pat):
    """
    Collect WiFi test tuples from files.  File names are used to
    sort the test objects so the convention is to name them NNN<test>
    where NNN is a decimal number used to sort and <test> is an
    identifying name for the test; e.g. 000Check11b
    """
    tests = []
    for file in os.listdir(dir):
        if fnmatch.fnmatch(file, pat):
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

