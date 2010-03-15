# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import common, fnmatch, logging, os, re, string, threading, time

from autotest_lib.server import autotest, subcommand
from autotest_lib.server import site_bsd_router
#from autotest_lib.server import site_linux_router

class HelperThread(threading.Thread):
    # Class that wraps a ping command in a thread so it can run in the bg.
    def __init__(self, client, cmd):
        threading.Thread.__init__(self)
        self.client = client
        self.cmd = cmd

    def run(self):
        # NB: set ignore_status as we're always terminated w/ pkill
        self.client.run(self.cmd, ignore_status=True)


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
      client_check_config     check the client network connection to verify
                              state is setup as expected
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
        self.client = client['host']
        self.client_at = autotest.Autotest(self.client)
        self.client_wifi_ip = None       # client's IP address on wifi net
        self.server = server['host']
        self.server_at = autotest.Autotest(self.server)
        # server's IP address on wifi net (XXX assume same for now)
        self.server_wifi_ip = self.server.ip

        # NB: truncate SSID to 32 characters
        self.defssid = self.__get_defssid()[0:32]

        # XXX auto-detect router type
        self.wifi = site_bsd_router.BSDRouter(self.router, router, self.defssid)

        # potential bg thread for ping untilstop
        self.ping_thread = None


    def setup(self):
        self.job.setup_dep(['netperf'])
# XXX enable once built by build_autotest
#        self.job.setup_dep(['iperf'])
        # create a empty srcdir to prevent the error that checks .version
        if not os.path.exists(self.srcdir):
            os.mkdir(self.srcdir)


    def cleanup(self, params):
        """ Cleanup state: disconnect client and destroy ap """
        self.disconnect({})
        self.wifi.destroy({})


    def __get_defssid(self):
        #
        # Calculate ssid based on test name; this lets us track progress
        # by watching beacon frames.
        #
        # XXX truncate to 32 chars
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

            logging.info("%s: step '%s' params %s" % \
                (self.name, method, params))

            func = getattr(self, method, None)
            if func is None:
                func = getattr(self.wifi, method, None)
            if func is not None:
                try:
                    func(params)
                except Exception, e:
                    logging.error("%s: Step '%s' failed: %s; abort test" % \
                        (self.name, method, str(e)))
                    self.cleanup(params)
                    break
            else:
                logging.error("%s: Step '%s' unknown; abort test" % \
                    (self.name, method))
                self.cleanup(params)
                break


    def __get_connect_script(self, params):
        return '\
import dbus, dbus.mainloop.glib, gobject, logging, re, sys, time\n\
\
ssid = "' + params['ssid'] + '"\n\
security = "' + params['security'] + '"\n\
psk = "' + params.get('psk', "") + '"\n\
assoc_timeout = ' + params.get('assoc_timeout', "15") + '\n\
config_timeout = ' + params.get('config_timeout', "15") + '\n\
\
bus_loop = dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)\n\
bus = dbus.SystemBus(mainloop=bus_loop)\n\
manager = dbus.Interface(bus.get_object("org.moblin.connman", "/"),\n\
    "org.moblin.connman.Manager")\n\
\
try:\n\
    path = manager.GetService(({\n\
        "Type": "wifi",\n\
        "Mode": "managed",\n\
        "SSID": ssid,\n\
        "Security": security,\n\
        "Passphrase": psk }))\n\
    service = dbus.Interface(\n\
        bus.get_object("org.moblin.connman", path),\n\
        "org.moblin.connman.Service")\n\
except Exception, e:\n\
    print "FAIL(GetService): ssid %s exception %s" %(ssid, e)\n\
    sys.exit(1)\n\
\
try:\n\
    service.Connect()\n\
except Exception, e:\n\
    print "FAIL(Connect): ssid %s exception %s" %(ssid, e)\n\
    sys.exit(2)\n\
\
status = ""\n\
assoc_time = 0\n\
# wait up to assoc_timeout seconds to associate\n\
while assoc_time < assoc_timeout:\n\
    properties = service.GetProperties()\n\
    status = properties.get("State", None)\n\
#    print>>sys.stderr, "time %3.1f state %s" % (assoc_time, status)\n\
    if status == "failure":\n\
        print "FAIL(assoc): ssid %s assoc %3.1f secs props %s" %(ssid, assoc_time, properties)\n\
        sys.exit(3)\n\
    if status == "configuration" or status == "ready":\n\
        break\n\
    time.sleep(.5)\n\
    assoc_time += .5\n\
if assoc_time >= assoc_timeout:\n\
    print "TIMEOUT(assoc): ssid %s assoc %3.1f secs" %(ssid, assoc_time)\n\
    sys.exit(4)\n\
\
# wait another config_timeout seconds to get an ip address\n\
config_time = 0\n\
if status != "ready":\n\
    while config_time < config_timeout:\n\
        properties = service.GetProperties()\n\
        status = properties.get("State", None)\n\
#        print>>sys.stderr, "time %3.1f state %s" % (config_time, status)\n\
        if status == "failure":\n\
            print "FAIL(config): ssid %s assoc %3.1f config %3.1f secs" \\\n\
                %(ssid, assoc_time, config_time)\n\
            sys.exit(5)\n\
        if status == "ready":\n\
            break\n\
        time.sleep(.5)\n\
        config_time += .5\n\
    if config_time >= config_timeout:\n\
        print "TIMEOUT(config): ssid %s assoc %3.1f config %3.1f secs"\\\n\
            %(ssid, assoc_time, config_time)\n\
        sys.exit(6)\n\
print "assoc %3.1f secs config %3.1f secs" % (assoc_time, config_time)\n\
sys.exit(0)'


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
        # XXX wlan0 hard coded
        self.client_wifi_ip = self.__get_ipaddr(self.client, "wlan0")
        logging.info("%s: client WiFi-IP is %s" % \
            (self.name, self.client_wifi_ip))


    def __make_disconnect_script(self, params):
        return '\
import dbus, dbus.mainloop.glib, gobject, logging, sys, time\n\
\n\
interface = "' + params.get('psk', "") + '"\n\
\n\
bus_loop = dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)\n\
bus = dbus.SystemBus(mainloop=bus_loop)\n\
manager = dbus.Interface(bus.get_object("org.moblin.connman", "/"),\n\
    "org.moblin.connman.Manager")\n\
\n\
sys.exit(0)'


    def disconnect(self, params):
        """ Disconnect previously connected client """
        self.client_ping_bg_stop({})
#        script = self.__make_disconnect_script(params)
#        self.client.run("python<<'EOF'\n%s\nEOF\n" % script)


    def sleep(self, params):
        time.sleep(float(params['time']))


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
        logging.info("%s: %s%s/%s, %s%% loss, rtt %s/%s/%s" % \
            (self.name, label, stats['xmit'], stats['recv'], stats['loss'],
             stats['min'], stats['avg'], stats['max']))


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
        ping_ip = params.get('ping_ip', self.client_wifi_ip)
        # XXX 30 second timeout
        result = self.server.run("ping %s %s" % \
           (self.__ping_args(params), ping_ip), timeout=30)

        self.__print_pingstats("server_ping ",
            self.__get_pingstats(result.stdout))



    def __run_iperf(self, client_ip, server_ip, params):
        template = ''.join(["job.run_test('iperf', \
            server_ip='%s', client_ip='%s', role='%s'%s"])
        if 'udp' in params:
            template += ", udp=True"
        if 'bidir' in params:
            template += ", bidirectional=True"
        if 'time' in params:
            template += ", test_time=%s" % params['time']
        template += ")"

        server_control_file = template % (server_ip, client_ip, 'server')
        server_command = subcommand.subcommand(self.server_at.run,
               [server_control_file, self.server.hostname])

        client_control_file = template % (server_ip, client_ip, 'client')
        client_command = subcommand.subcommand(self.client_at.run,
               [client_control_file, self.client.hostname])

        logging.info("%s: iperf %s => %s" % (self.name, client_ip, server_ip))

        # XXX 30 sec timeout for now
        subcommand.parallel([server_command, client_command], timeout=30)


    def client_iperf(self, params):
        """ Run iperf on the client against the server """
        self.__run_iperf(self.client_wifi_ip, self.server_wifi_ip, params)


    def server_iperf(self, params):
        """ Run iperf on the server against the client """
        self.__run_iperf(self.server_wifi_ip, self.client_wifi_ip, params)


    def __run_netperf(self, client_ip, server_ip, params):
        template = ''.join(["job.run_test('netperf2', \
            server_ip='%s', client_ip='%s', role='%s'"])
        if 'test' in params:
            template += ", test='%s'" % params['test']
        if 'bidir' in params:
            template += ", bidi=True"
        if 'time' in params:
            template += ", test_time=%s" % params['time']
        template += ")"

        server_control_file = template % (server_ip, client_ip, 'server')
        server_command = subcommand.subcommand(self.server_at.run,
               [server_control_file, self.server.hostname])

        client_control_file = template % (server_ip, client_ip, 'client')
        client_command = subcommand.subcommand(self.client_at.run,
               [client_control_file, self.client.hostname])

        logging.info("%s: netperf %s => %s" % (self.name, client_ip, server_ip))

        # XXX 30 sec timeout for now
        subcommand.parallel([server_command, client_command], timeout=60)


    def client_netperf(self, params):
        """ Run netperf on the client against the server """
        self.__run_netperf(self.client_wifi_ip, self.server_wifi_ip, params)


    def server_netperf(self, params):
        """ Run netperf on the server against the client """
        self.__run_netperf(self.server_wifi_ip, self.client_wifi_ip, params)


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
                logging.error("%s: %s" % (os.path.join(dir, file), str(e)))
                raise e
            test['file'] = file
            tests.append(test)
    # use filenames to sort
    return sorted(tests, cmp=__byfile)

