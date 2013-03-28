# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re

from autotest_lib.client.common_lib import error
from autotest_lib.server import site_linux_system
from autotest_lib.server.cros import remote_command
from autotest_lib.server.cros import wifi_test_utils

class LinuxServer(site_linux_system.LinuxSystem):
    """
    Linux Server: A machine which hosts network services.

    """

    COMMAND_PING = '/usr/bin/ping'
    COMMAND_NETPERF = '/usr/bin/netperf'
    COMMAND_NETSERVER = '/usr/bin/netserver'
    COMMAND_IP = '/usr/sbin/ip'
    COMMAND_IPERF = '/usr/bin/iperf'


    def __init__(self, server, config):
        site_linux_system.LinuxSystem.__init__(self, server, {}, "server")

        self._server                     = server    # Server host.
        self.vpn_kind                    = None
        self.config                      = config
        self.openvpn_config              = {}
        self.radvd_config                = {'file':'/tmp/radvd-test.conf',
                                            'server':'/usr/sbin/radvd'}

        # Check that tools we require from WiFi test servers exist.
        self._cmd_netperf = wifi_test_utils.must_be_installed(
                self._server, LinuxServer.COMMAND_NETPERF)
        self._cmd_netserver = wifi_test_utils.must_be_installed(
                self._server, LinuxServer.COMMAND_NETSERVER)
        self._cmd_ip = wifi_test_utils.must_be_installed(
                self._server, LinuxServer.COMMAND_IP)
        self._cmd_iperf = wifi_test_utils.must_be_installed(
                self._server, LinuxServer.COMMAND_IPERF)
        # /usr/bin/ping is preferred, as it is likely to be iputils.
        if wifi_test_utils.is_installed(self._server,
                                        LinuxServer.COMMAND_PING):
            self._cmd_ping = LinuxServer.COMMAND_PING
        else:
            self._cmd_ping = 'ping'

        self._ping_bg_job = None
        self._wifi_ip = None


    @property
    def cmd_netperf(self):
        """ @return string full path to start netperf. """
        return self._cmd_netperf


    @property
    def cmd_netserv(self):
        """ @return string full path to start netserv. """
        return self._cmd_netserver


    @property
    def cmd_iperf(self):
        """ @return string full path to start iperf. """
        return self._cmd_iperf


    @property
    def cmd_ping(self):
        """ @return string full path to start ping. """
        return self._cmd_ping


    @property
    def server(self):
        """ @return Host object for this remote server. """
        return self._server


    @property
    def wifi_ip(self):
        """
        Returns an IP address pingable from the client DUT.

        Throws an error if no interface is configured with a potentially
        pingable IP.

        @return String IP address on the WiFi subnet.
        """
        if not self._wifi_ip:
            addrs = self._get_system_ipv4_addrs(self.server)
            # Discard loopback IPs and the control network IP.
            valid_addrs = filter(
                    lambda addr: not addr.startswith('127.0.0') and
                                 not addr.startswith(self.server.ip),
                    addrs)
            if not valid_addrs:
                raise error.TestFailed('No configured interfaces.')
            if len(valid_addrs) > 1:
                logging.warning('Multiple interfaces configured on server; '
                                'taking first.')
            self._wifi_ip = valid_addrs[0]
        return self._wifi_ip


    def _get_system_ipv4_addrs(self, host):
        """
        Returns a list of IPs configured on host.

        @param host Host object representing a remote machine.
        @return list of IPv4 addresses as strings.

        """
        ip_output = host.run('%s -4 addr show' % self._cmd_ip).stdout
        regex = re.compile('^inet ([0-9]{1,3}(\\.[0-9]{1,3}){3})')
        ips = []
        for line in ip_output.splitlines():
            ip = re.search(regex, line.strip())
            if ip:
                # Group 1 will be the IP address following 'inet addr:'.
                ips.append(ip.group(1))
        return ips


    def vpn_server_config(self, params):
        """ Configure & launch the server side of the VPN.

            Parameters, in 'params':

               kind  : required

                       The kind of VPN which should be configured and
                       launched.

                       Valid values:

                          openvpn
                          l2tpipsec (StrongSwan PSK or certificates)

               config: required

                       The configuration information associated with
                       the VPN server.

                       This is a dict which contains key/value pairs
                       representing the VPN's configuration.

          The values stored in the 'config' param must all be
          supported by the specified VPN kind.
        """
        self.vpn_server_kill({}) # Must be first.  Relies on self.vpn_kind.
        self.vpn_kind = params.get('kind', None)

        # Launch specified VPN server.
        if self.vpn_kind is None:
            raise error.TestFail('No VPN kind specified for this test.')
        elif self.vpn_kind == 'openvpn':
            # Read config information & create server configuration file.
            for k, v in params.get('config', {}).iteritems():
                self.openvpn_config[k] = v
            self.server.run("cat <<EOF >/tmp/vpn-server.conf\n%s\nEOF\n" %
                            ('\n'.join( "%s %s" % kv for kv in
                                        self.openvpn_config.iteritems())))
            self.server.run("/usr/sbin/openvpn "
                            "--config /tmp/vpn-server.conf &")
        elif self.vpn_kind in ('l2tpipsec-psk', 'l2tpipsec-cert'):
            configs = {
                "/etc/xl2tpd/xl2tpd.conf" :
                "[global]\n"
                "\n"
                "[lns default]\n"
                "  ip range = 192.168.1.128-192.168.1.254\n"
                "  local ip = 192.168.1.99\n"
                "  require chap = yes\n"
                "  refuse pap = yes\n"
                "  require authentication = yes\n"
                "  name = LinuxVPNserver\n"
                "  ppp debug = yes\n"
                "  pppoptfile = /etc/ppp/options.xl2tpd\n"
                "  length bit = yes\n",

                "/etc/xl2tpd/l2tp-secrets" :
                "*      them    l2tp-secret",

                "/etc/ppp/chap-secrets" :
                "chapuser        *       chapsecret      *",

                "/etc/ppp/options.xl2tpd" :
                "ipcp-accept-local\n"
                "ipcp-accept-remote\n"
                "noccp\n"
                "auth\n"
                "crtscts\n"
                "idle 1800\n"
                "mtu 1410\n"
                "mru 1410\n"
                "nodefaultroute\n"
                "debug\n"
                "lock\n"
                "proxyarp\n"
                "connect-delay 5000\n"
            }
            config_choices = {
              'l2tpipsec-psk': {
                  "/etc/ipsec.conf" :
                  "config setup\n"
                  "  charonstart=no\n"
                  "  plutostart=yes\n"
                  "  plutodebug=%(@plutodebug@)s\n"
                  "  plutostderrlog=/var/log/pluto.log\n"
                  "conn L2TP\n"
                  "  keyexchange=ikev1\n"
                  "  authby=psk\n"
                  "  pfs=no\n"
                  "  rekey=no\n"
                  "  left=%(@local-listen-ip@)s\n"
                  "  leftprotoport=17/1701\n"
                  "  right=%%any\n"
                  "  rightprotoport=17/%%any\n"
                  "  auto=add\n",

                  "/etc/ipsec.secrets" :
                  "%(@ipsec-secrets@)s %%any : PSK \"password\"",
                },
                'l2tpipsec-cert': {
                    "/etc/ipsec.conf" :
                    "config setup\n"
                    "  charonstart=no\n"
                    "  plutostart=yes\n"
                    "  plutodebug=%(@plutodebug@)s\n"
                    "  plutostderrlog=/var/log/pluto.log\n"
                    "conn L2TP\n"
                    "  keyexchange=ikev1\n"
                    "  left=%(@local-listen-ip@)s\n"
                    "  leftcert=server.crt\n"
                    "  leftid=\"C=US, ST=California, L=Mountain View, "
                    "CN=chromelab-wifi-testbed-server.mtv.google.com\"\n"
                    "  leftprotoport=17/1701\n"
                    "  right=%%any\n"
                    "  rightca=\"C=US, ST=California, L=Mountain View, "
                    "CN=chromelab-wifi-testbed-root.mtv.google.com\"\n"
                    "  rightprotoport=17/%%any\n"
                    "  auto=add\n"
                    "  pfs=no\n",

                    "/etc/ipsec.secrets" : ": RSA server.key \"\"\n",
                },
            }
            configs.update(config_choices[self.vpn_kind])

            replacements = params.get("replacements", {})
            # These two replacements must match up to the same
            # adapter, or a connection will not be established.
            replacements["@local-listen-ip@"] = "%defaultroute"
            replacements["@ipsec-secrets@"]   = self.server.ip

            for cfg, template in configs.iteritems():
                contents = template % (replacements)
                self.server.run("cat <<EOF >%s\n%s\nEOF\n" % (cfg, contents))

            self.server.run("/usr/sbin/ipsec restart")

            # Restart xl2tpd to ensure use of newly-created config files.
            self.server.run("sh /etc/init.d/xl2tpd restart")
        else:
            raise error.TestFail('(internal error): No config case '
                                 'for VPN kind (%s)' % self.vpn_kind)


    def vpn_server_kill(self, params):
        """ Kill the VPN server. """
        if self.vpn_kind is not None:
            if self.vpn_kind == 'openvpn':
                self.server.run("pkill /usr/sbin/openvpn")
            elif self.vpn_kind in ('l2tpipsec-psk', 'l2tpipsec-cert'):
                self.server.run("/usr/sbin/ipsec stop")
            else:
                raise error.TestFail('(internal error): No kill case '
                                     'for VPN kind (%s)' % self.vpn_kind)
            self.vpn_kind = None


    def ipv6_server_config(self, params):
        self.ipv6_server_kill({})
        radvd_opts = { 'interface': self.config.get('server_dev', 'eth0'),
                       'adv_send_advert': 'on',
                       'min_adv_interval': '3',
                       'max_adv_interval': '10',
                       # NB: Addresses below are within the 2001:0db8/32
                       # "documentation only" prefix (RFC3849), which is
                       # guaranteed never to be assigned to a real network.
                       'prefix': '2001:0db8:0100:f101::/64',
                       'adv_on_link': 'on',
                       'adv_autonomous': 'on',
                       'adv_router_addr': 'on',
                       'rdnss_servers': '2001:0db8:0100:f101::0001 '
                                        '2001:0db8:0100:f101::0002',
                       'adv_rdnss_lifetime': 'infinity',
                       'dnssl_list': 'a.com b.com' }
        radvd_opts.update(params)

        config = ('interface %(interface)s {\n'
                  '  AdvSendAdvert %(adv_send_advert)s;\n'
                  '  MinRtrAdvInterval %(min_adv_interval)s;\n'
                  '  MaxRtrAdvInterval %(max_adv_interval)s;\n'
                  '  prefix %(prefix)s {\n'
                  '    AdvOnLink %(adv_on_link)s;\n'
                  '    AdvAutonomous %(adv_autonomous)s;\n'
                  '    AdvRouterAddr %(adv_router_addr)s;\n'
                  '  };\n'
                  '  RDNSS %(rdnss_servers)s {\n'
                  '    AdvRDNSSLifetime %(adv_rdnss_lifetime)s;\n'
                  '  };\n'
                  '  DNSSL %(dnssl_list)s {\n'
                  '  };\n'
                  '};\n') % radvd_opts
        cfg_file = params.get('config_file', self.radvd_config['file'])
        self.server.run('cat <<EOF >%s\n%s\nEOF\n' % (cfg_file, config))
        self.server.run('%s -C %s\n' % (self.radvd_config['server'], cfg_file))


    def ipv6_server_kill(self, params):
        self.server.run('pkill %s >/dev/null 2>&1' %
                        self.radvd_config['server'], ignore_status=True)


    def ping(self, ping_ip, count, ping_params):
        """
        Ping a client from the server.

        Ping |ping_ip| |count| times using options to ping specified in
        |ping_params|.

        @param ping_ip String containing a client IP address.
        @param count String number of times to ping the client.
        @param ping_params dict of settings for ping.
        @return dict of ping statistics.

        """
        # set timeout for 3s / ping packet
        ping_params = ping_params.copy()
        ping_params['count'] = str(count)
        cmd = "%s %s %s" % (self.cmd_ping,
                            wifi_test_utils.ping_args(ping_params),
                            ping_ip)
        result = self.server.run(cmd, timeout=3*int(count))
        return wifi_test_utils.parse_ping_output(result.stdout)


    def ping_bg(self, ping_ip, ping_params):
        """
        Ping a client from the server in a background thread.

        Ping |ping_ip| using options to ping specified in
        |ping_params| in the background.  This call does not block.

        @param ping_ip String containing a client IP address.
        @param ping_params dict of settings for ping.

        """
        cmd = "%s %s %s" % (self.cmd_ping,
                            wifi_test_utils.ping_args(ping_params),
                            ping_ip)
        self._ping_bg_job = remote_command.Command(self.server, cmd)


    def ping_bg_stop(self):
        """
        Stop pinging the client in the background.

        """
        if self._ping_bg_job is not None:
            self._ping_bg_job.join()
            self._ping_bg_job = None
