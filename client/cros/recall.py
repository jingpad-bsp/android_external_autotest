# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Context Manager for using Recall in autotest tests.

Recall is a server-side system that intercepts DNS, HTTP and HTTPS
traffic from clients for either recording or playback. This allows
tests to be run in labs without Internet access by playing back
pre-recorded copies of websites, allows tests to be run that use
recorded copies of sites known to exhibit errors or many iterations
of the same test to be run with the same data.

Recall is intended to be completely transparent to the client tests,
this context manager takes care of adjusting the client's configuration
to redirect the traffic to the recall server (in the case it's not the
network's default gateway already) and install a root certificate
for HTTPS man-in-the-middling.

It's instantiated as part of the control file sent from the autotest
server when invoking the client tests.
"""

import logging, os, re, stat, subprocess, urllib2

import common, constants
from autotest_lib.client.common_lib import error


class RecallServer(object):
    """Context manager for adjusting client configuration for Recall.

    Use this in a control file to wrap a client test to run against a
    server using Recall:

      with RecallServer(recall_server_ip):
          job.run_test(...)

    This is intended to be included in the control file passed from the
    autotest server to the client to be run.
    """

    def __init__(self, recall_server_ip):
        self._recall_server_ip = recall_server_ip

    def __enter__(self):
        certificate_url = ("http://%s/GetRootCertificate"
                           % self._recall_server_ip)
        self._InstallRootCertificate(certificate_url)
        self._InstallDnsServer(self._recall_server_ip)
        self._InstallDefaultRoute(self._recall_server_ip)

    def __exit__(self, exc_type, exc_value, traceback):
        self._UninstallRootCertificate()
        self._UninstallDnsServer()
        self._UninstallDefaultRoute()
        return False

    def _InstallRootCertificate(self, certificate_url):
        """Download fake root cert from server and install.

        Mounts a tmpfs filesystem over the location that Chromium will
        look for an additional nssdb, downloads a root certificate from
        the given URL and creates an nssdb containing it.

        Args:
            certificate_url: URL of certificate to download.
        """
        logging.debug("Obtaining certificate from %s", certificate_url)
        f = urllib2.urlopen(certificate_url)
        try:
            certificate = f.read()
        finally:
            f.close()

        logging.debug("Mounting tmpfs on %s", constants.FAKE_ROOT_CA_DIR)
        cmd = ( 'mount', '-t', 'tmpfs', '-o', 'mode=0755', 'none',
                constants.FAKE_ROOT_CA_DIR )
        proc = subprocess.Popen(cmd)
        proc.wait()
        if proc.returncode != 0:
            raise error.TestError("Failed to mount tmpfs")

        logging.debug("Creating NSS database in %s", constants.FAKE_NSSDB_DIR)
        os.mkdir(constants.FAKE_NSSDB_DIR, 0755)

        cmd = ( 'certutil', '-d', 'sql:' + constants.FAKE_NSSDB_DIR,
                '-N', '-f', '/dev/fd/0' )
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        proc.communicate('\n')
        if proc.returncode != 0:
            raise error.TestError("Failed to create nssdb")

        logging.debug("Adding certificate to database")
        cmd = ( 'certutil', '-d', 'sql:' + constants.FAKE_NSSDB_DIR,
                '-A', '-n', "Chromium OS Test Server", '-t', 'C,,', '-a' )
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        proc.communicate(certificate)
        if proc.returncode != 0:
            raise error.TestError("Failed to add certificate to nssdb")

        logging.debug("Fixing permissions")
        for filename in os.listdir(constants.FAKE_NSSDB_DIR):
            os.chmod(os.path.join(constants.FAKE_NSSDB_DIR, filename), 0644)

    def _UninstallRootCertificate(self):
        """Uninstall fake root cert.

        Unmounts the tmpfs created by _InstallRootCertificate().
        """
        logging.info("Unmounting tmpfs from %s", constants.FAKE_ROOT_CA_DIR)
        cmd = ( 'umount', '-l', constants.FAKE_ROOT_CA_DIR )
        proc = subprocess.Popen(cmd)
        proc.wait()
        if proc.returncode != 0:
            raise error.TestError("Failed to umount tmpfs")

    def _InstallDnsServer(self, nameserver):
        """Change the system DNS server.

        Backs up and writes out an alternate /etc/resolv.conf pointing
        at the nameserver given.

        Args:
            nameserver: IP address of server to use.
        """
        resolv_conf = os.path.realpath(constants.RESOLV_CONF_FILE)
        resolv_conf_bak = resolv_conf + '.recallbak'
        resolv_dir = os.path.dirname(resolv_conf)

        logging.info("Changing nameserver to %s", nameserver)
        os.rename(resolv_conf, resolv_conf_bak)
        with open(resolv_conf, 'w') as resolv:
            self._resolv_dir_mode = os.stat(resolv_dir).st_mode
            os.chmod(resolv_dir, self._resolv_dir_mode & ~ (stat.S_IWUSR |
                                                            stat.S_IWGRP |
                                                            stat.S_IWOTH))

            print >>resolv, "nameserver %s" % nameserver

    def _UninstallDnsServer(self):
        """Restore the system DNS server.

        Restores the original /etc/resolv.conf from before calling
        _InstallDnsServer().
        """
        resolv_conf = os.path.realpath(constants.RESOLV_CONF_FILE)
        resolv_conf_bak = resolv_conf + '.recallbak'
        resolv_dir = os.path.dirname(resolv_conf)

        logging.info("Restoring original nameserver")
        os.chmod(resolv_dir, self._resolv_dir_mode)
        os.rename(resolv_conf_bak, resolv_conf)

    def _GetDefaultRouteGateway(self):
        """Return the gateway of the default route."""
        cmd = ( 'ip', 'route', 'show' )
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        data, errdata = proc.communicate()
        if proc.returncode != 0:
            raise error.TestError("Failed to obtain routing table")

        for line in data.splitlines():
            if not line.startswith("default "):
                continue

            match = re.search(r'via ([^ ]*)', line)
            if not match:
                continue

            return match.group(1)
        else:
            raise error.TestError("Failed to obtain default route gateway")

    def _InstallDefaultRoute(self, gateway):
        """Change the gateway of the default route.

        Adjusts the system routing table so that the gateway of the
        default route points to the IP address given.

        Args:
            gateway: IP address of new default route gateway.
        """
        self._original_gateway = self._GetDefaultRouteGateway()

        logging.info("Changing default route gateway to %s", gateway)
        cmd = ( 'ip', 'route', 'change', 'default', 'via', gateway )
        proc = subprocess.Popen(cmd)
        proc.wait()
        if proc.returncode != 0:
            raise error.TestError("Failed to change default route gateway")

        cmd = ( 'ip', 'route', 'flush', 'cache')
        proc = subprocess.Popen(cmd)
        proc.wait()
        # Discard return code, it doesn't matter so much if this fails

    def _UninstallDefaultRoute(self):
        """Restore the gateway of the default route.

        Restores the gateway of the default route to that which existed
        before calling _InstallDefaultRoute().
        """
        logging.info("Restoring original default route gateway")
        cmd = ( 'ip', 'route', 'change', 'default', 'via',
                self._original_gateway )
        proc = subprocess.Popen(cmd)
        proc.wait()
        if proc.returncode != 0:
            raise error.TestError("Failed to change default route gateway")

        cmd = ( 'ip', 'route', 'flush', 'cache')
        proc = subprocess.Popen(cmd)
        proc.wait()
        # Discard return code, it doesn't matter so much if this fails
