# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, re, time
from autotest_lib.client.common_lib import error

class LinuxServer(object):
    """
    Linux Server: A machine which hosts network services.

    """

    def __init__(self, server, params):
        self.server   = server    # Server host.
        self.vpn_kind = None
        self.conf     = {}

    def vpn_server_config(self, params):
        """ Configure & launch the server side of the VPN.

            Parameters, in 'params':

               kind  : required

                       The kind of VPN which should be configured and
                       launched.

                       Valid values:

                          openvpn

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

        # Read configuration information & create server configuration file.
        #
        #    As VPN kinds other than 'openvpn' are supported, and
        #    since 'self.conf' is cummulative, perhaps there should be
        #    a method which will clear 'self.conf'; different types of
        #    VPN will likely not have the same configuration
        #    parameters.  This is only really needed if a test is
        #    written to switch between two differents kinds of VPN.
        for k, v in params.get('config', {}).iteritems():
            self.conf[k] = v
        self.server.run("cat <<EOF >%s\n%s\nEOF\n" %
                        ('/tmp/vpn-server.conf', '\n'.join(
                    "%s %s" % kv for kv in self.conf.iteritems())))

        # Launch specified VPN server.
        if self.vpn_kind is None:
            raise error.TestFail('No VPN kind specified for this test.');
        elif self.vpn_kind == 'openvpn':
            self.server.run("/usr/sbin/openvpn --config /tmp/vpn-server.conf &")
        else:
            raise error.TestFail('(internal error): No config case '
                                 'for VPN kind (%s)' % self.vpn_kind)

    def vpn_server_kill(self, params):
        """ Kill the VPN server. """
        if self.vpn_kind is not None:
            if self.vpn_kind == 'openvpn':
                self.server.run("pkill /usr/sbin/openvpn")
            else:
                raise error.TestFail('(internal error): No kill case '
                                     'for VPN kind (%s)' % self.vpn_kind)
            self.vpn_kind = None;
