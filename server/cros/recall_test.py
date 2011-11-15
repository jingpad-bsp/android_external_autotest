# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Base class for Recall tests.

Recall provides an infrastructure for proxying, recording, altering and
playing back DNS, HTTP and HTTPS requests.

This requires that an autotest server test be run, with some configuration
changes to the server, and then the desired client test run on the client
wrapped with the Recall context manager.

The server test base class provided handles most of the heavy lifting for
you. For an example server test, see test_RecallServer that implements the
common case of recording and playback.
"""

import errno
import logging
import os
import re
import subprocess

from autotest_lib.client.common_lib import error
from autotest_lib.server import test, autotest
from autotest_lib.server.cros import recall


class RecallServerTest(test.test):
    """AutoTest test class for Recall tests.

    This base class handles adjusting the autotest server configuration
    to allow redirection of traffic from the remote client to it, and
    cleaning up afterwards.

    Subclasses should override the initialize method and setup the
    following members before calling the superclass method:

        certificate_authority: instance of recall.CertificateAuthority to
            use to generate or retrieve certificates.
        dns_client: instance of recall.DNSClient or compatible class to
            lookup DNS results.
        http_client: instance of recall.HTTPClient or compatible class to
            lookup HTTP results.

    If these are left as None, no appropriate server will be created by
    this method. The subclass may then choose to set up servers of its
    own and use InstallPortRedirect() to redirect traffic to them.

    Members available for use by subclasses:

        ANY_ADDRESS: pass to SocketServer instances to get a random port.

        source_address: local IP address that will likely be used to
            communicate with the remote client.
        source_interface: local interface of source_address.

        dns_server: recall.DNSServer created using dns_client.
        http_server: recall.HTTPServer created using http_client.
        https_server: recall.HTTPSServer created using http_client.

    Finally to run the client test on the remote client the subclass
    should call RunTestOnHost() in its run_once() function.
    """
    version = 1

    # Pass as server_address to SocketServer classes to get a random port
    ANY_ADDRESS = ('', 0)

    _send_redirects_sysctl_pattern = "net.ipv4.conf.%s.send_redirects"

    def __init__(self, job, bindir, outputdir):
        test.test.__init__(self, job, bindir, outputdir)

        # To be set by subclass initialize
        self.certificate_authority = None
        self.dns_client = None
        self.http_client = None

        # Set by our initialize
        self.dns_server = None
        self.http_server = None
        self.https_server = None

        self._send_redirects = None
        self._port_redirects = []

    def initialize(self, host):
        """Initialize the Recall server.

        Override in your subclass to setup the certificate_authority,
        dns_client and http_client members before calling the superclass
        method.

        You may also leave those as None and setup your own server
        instances if you prefer.

        This method sets the source_address and source_interface members
        to the local address and interface that would be used to reach
        the given host.

        Args:
            host: autotest host object for remote client.
        """
        if host.ip == '127.0.0.1':
            raise error.TestError("Recall server tests cannot be run against "
                                  "the autotest server or a VM running on it.")

        self._host = host
        self.source_address, self.source_interface = \
            self._GetAddressAndInterfaceForAddress(self._host.ip)
        logging.debug("Source address and interface for %s are %s, %s",
                      self._host.ip,
                      self.source_address, self.source_interface)

        # Disable ICMP redirects for the interface we use for the client
        self._send_redirects_sysctl = self._send_redirects_sysctl_pattern \
            % self.source_interface
        try:
            self._send_redirects = \
                self._GetAndSetSysctl(self._send_redirects_sysctl, '0')
        except IOError as e:
            if e.errno == errno.EACCES:
                raise error.TestError("Recall server tests must be run as root")
            else:
                raise

        # Setup the servers using the client classes provided
        if self.dns_client is not None:
            logging.info("Setting up DNS Server")
            self.dns_server = recall.DNSServer(self.ANY_ADDRESS,
                                               self.dns_client)
            self.InstallPortRedirect('udp', 53,
                                     self.dns_server.server_address[-1])
            self.InstallPortRedirect('tcp', 53,
                                     self.dns_server.server_address[-1])
        if self.http_client is not None:
            logging.info("Setting up HTTP and HTTPS Server")
            self.http_server = recall.HTTPServer(
                self.ANY_ADDRESS, self.http_client, self.dns_client,
                self.certificate_authority)
            self.InstallPortRedirect('tcp', 80,
                                     self.http_server.server_address[-1])

            if self.certificate_authority is not None:
                self.https_server = recall.HTTPSServer(
                    self.ANY_ADDRESS, self.http_client, self.dns_client,
                    self.certificate_authority)
                self.InstallPortRedirect('tcp', 443,
                                     self.https_server.server_address[-1])

    def cleanup(self):
        """Cleanup.

        If you override in your subclass, be sure to call the superclass
        method.
        """
        self._UninstallPortRedirects()

        if self._send_redirects is not None:
          self._GetAndSetSysctl(self._send_redirects_sysctl,
                                self._send_redirects)

        if self.dns_server is not None:
            self.dns_server.shutdown()
        if self.http_server is not None:
            self.http_server.shutdown()
        if self.https_server is not None:
            self.https_server.shutdown()

    def _GetAddressAndInterfaceForAddress(self, ip_address):
        """Return the local address and interface to reach an address.

        Given the IP address of a remote machine, returns the local
        source address and interface that may be used to reach that
        machine.

        This may not be the actual return IP address the remote machine
        sees if a NAT or similar redirection is in the way, but if
        they are on the same local network, it should resolve cases of
        multiple interfaces.

        Args:
            ip_address: address of remote machine as string.

        Returns:
            tuple of local address and interface names as strings.
        """
        cmd = ( '/sbin/ip', 'route', 'get', ip_address )
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        data, errdata = proc.communicate()
        if proc.returncode != 0:
            raise error.TestError("Failed to obtain local address for remote")

        match = re.search(r'src ([^ ]*)', data)
        if not match:
            raise error.TestError("Missing source address for remote")
        source = match.group(1)

        match = re.search(r'dev ([^ ]*)', data)
        if not match:
            raise error.TestError("Missing source device for remote")
        interface = match.group(1)

        return source, interface

    def _GetAndSetSysctl(self, sysctl_name, new_value=None):
        """Sets a sysctl, returning the old value.

        Args:
            sysctl_name: dotted-notation name of sysctl.
            new_value: new value, if None, only returns current value.
        """
        sysctl_path = os.path.join('/proc/sys', sysctl_name.replace('.', '/'))
        with open(sysctl_path, 'r+') as sysctl:
            old_value = sysctl.read()
            if new_value is not None:
                print >>sysctl, new_value

        return old_value

    def InstallPortRedirect(self, protocol, port, to_port):
        """Install a port redirection.

        Installs a port direction so that requests from the client for the
        given protocol and port are redirected to the local port given.

        Can be removed with _UninstallPortRedirects().

        Args:
            protocol: protocol to redirect ('tcp' or 'udp').
            port: integer port to redirect, or tuple of range to redirect.
            to_port: integer port to redirect to on current machine.
        """
        try:
            port_spec = ':'.join(str(p) for p in port)
        except TypeError:
            port_spec = str(port)

        logging.debug("Installing port redirection for %s %s -> %d",
                      protocol, port_spec, to_port)
        cmd = ( '/sbin/iptables', '-t', 'nat', '-A', 'PREROUTING',
                '-p', protocol, '-s', self._host.ip,
                '--dport', port_spec, '-j', 'REDIRECT',
                '--to-ports', '%d' % to_port )
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        proc.wait()
        if proc.returncode != 0:
            raise error.TestError("Failed to install port redirection")

        self._port_redirects.append((protocol, port_spec, to_port))

    def _UninstallPortRedirects(self):
        """Uninstall port redirections.

        Removes all port redirects installed with _InstallPortRedirect().
        """
        for protocol, port_spec, to_port in self._port_redirects:
            cmd = ( '/sbin/iptables', '-t', 'nat', '-D', 'PREROUTING',
                    '-p', protocol, '-s', self._host.ip,
                    '--dport', port_spec, '-j', 'REDIRECT',
                    '--to-ports', '%d' % to_port )
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            proc.wait()
            if proc.returncode != 0:
                raise error.TestError("Failed to uninstall port redirection")

    def RunTestOnHost(self, test, host, **args):
        """Run client test on host using this Recall server.

        Args:
            test: name of test to run.
            host: host object to run test on.

        Additional keyword arguments are passed as arguments to the test
        being run.
        """
        # (keybuk) don't hurt me, I copied this code from autotest itself
        opts = ["%s=%s" % (o[0], repr(o[1])) for o in args.items()]
        cmd = ", ".join([repr(test)] + opts)
        control = """\
from autotest_lib.client.cros.recall import RecallServer
with RecallServer(%r):
    job.run_test(%s)
""" % (self.source_address, cmd)

        logging.debug("Running control file %s", control)

        client_autotest = autotest.Autotest(host)
        return client_autotest.run(control)
