# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, re, time
from autotest_lib.client.common_lib import error
from autotest_lib.server import site_linux_system

class LinuxServer(site_linux_system.LinuxSystem):
    """
    Linux Server: A machine which hosts network services.

    """

    def __init__(self, server, wifi_ip):
        site_linux_system.LinuxSystem.__init__(self, server, {}, "server")

        self.server                      = server    # Server host.
        self.vpn_kind                    = None
        self.wifi_ip                     = wifi_ip
        self.openvpn_config              = {}

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
