# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#

"""This file provides core logic for connecting a Chameleon Daemon."""


import xmlrpclib

from autotest_lib.client.bin import utils
from autotest_lib.server.hosts import ssh_host


def make_chameleon_hostname(dut_hostname):
    """Given a DUT's hostname, return the hostname of its Chameleon.

    @param dut_hostname: hostname of a DUT.

    @return hostname of the DUT's Chameleon.

    """
    host_parts = dut_hostname.split('.')
    host_parts[0] = host_parts[0] + '-chameleon'
    return '.'.join(host_parts)


class ChameleonHost(ssh_host.SSHHost):
    """Host class for a host that controls a Chameleon."""

    # Chameleond process name.
    CHAMELEOND_PROCESS = 'chameleond'


    # TODO(waihong): Add verify and repair logic which are required while
    # deploying to Cros Lab.


    def _initialize(self, chameleon_host='localhost', chameleon_port=9992,
                    *args, **dargs):
        """Initialize a ChameleonHost instance.

        A ChameleonHost instance represents a host that controls a Chameleon.

        @param chameleon_host: Name of the host where the chameleond process
                               is running.
        @param chameleon_port: Port the chameleond process is listening on.

        """
        super(ChameleonHost, self)._initialize(hostname=chameleon_host,
                                               *args, **dargs)
        self._is_in_lab = utils.host_is_in_lab_zone(self.hostname)
        remote = 'http://%s:%s' % (self.hostname, chameleon_port)
        self._chameleond_proxy = xmlrpclib.ServerProxy(remote)


    def is_in_lab(self):
        """Check whether the chameleon host is a lab device.

        @returns: True if the chameleon host is in Cros Lab, otherwise False.

        """
        return self._is_in_lab


    def get_chameleond_proxy(self):
        """Return a proxy that can be used to communicate with chameleond.

        @returns: An xmlrpclib.ServerProxy that is connected to the chameleond
                  on the host.

        """
        return self._chameleond_proxy


    def get_wait_up_processes(self):
        """Get the list of local processes to wait for in wait_up.

        Override get_wait_up_processes in
        autotest_lib.client.common_lib.hosts.base_classes.Host.
        Wait for chameleond process to go up. Called by base class when
        rebooting the device.

        """
        processes = [self.CHAMELEOND_PROCESS]
        return processes

