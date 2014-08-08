# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import common
import logging
import re

from autotest_lib.client.common_lib import error, global_config
from autotest_lib.server.cros.dynamic_suite import frontend_wrappers
from autotest_lib.server.hosts import cros_host


AUTOTEST_INSTALL_DIR = global_config.global_config.get_config_value(
        'SCHEDULER', 'drone_installation_directory')
#'/usr/local/autotest'
SHADOW_CONFIG_PATH = '%s/shadow_config.ini' % AUTOTEST_INSTALL_DIR
ATEST_PATH = '%s/cli/atest' % AUTOTEST_INSTALL_DIR
SUBNET_DUT_SEARCH_RE = (
        r'/?.*\((?P<ip>192.168.231.*)\) at '
        '(?P<mac>[0-9a-fA-F][0-9a-fA-F]:){5}([0-9a-fA-F][0-9a-fA-F])')
MOBLAB_IMAGE_STORAGE = '/mnt/moblab/static'


class MoblabHost(cros_host.CrosHost):
    """Moblab specific host class."""


    def _initialize(self, *args, **dargs):
        super(MoblabHost, self)._initialize(*args, **dargs)
        self.afe = frontend_wrappers.RetryingAFE(timeout_min=1,
                                                 server=self.hostname)
        # Clear the Moblab Image Storage so that staging an image is properly
        # tested.
        self.run('rm -rf %s/*' % MOBLAB_IMAGE_STORAGE)
        # Ensure the autotest install directory exists.
        self.run('mkdir -p %s' % self.get_autodir())


    @staticmethod
    def check_host(host, timeout=10):
        """
        Check if the given host is an moblab host.

        @param host: An ssh host representing a device.
        @param timeout: The timeout for the run command.


        @return: True if the host device has adb.

        @raises AutoservRunError: If the command failed.
        @raises AutoservSSHTimeout: Ssh connection has timed out.
        """
        try:
            result = host.run('grep -q moblab /etc/lsb-release',
                              ignore_status=True, timeout=timeout)
        except (error.AutoservRunError, error.AutoservSSHTimeout):
            return False
        return result.exit_status == 0


    def get_autodir(self):
        """Return the directory to install autotest for client side tests."""
        return '/usr/local/autodir'


    def run_as_moblab(self, command, **kwargs):
        """Moblab commands should be ran as the moblab user not root.

        @param command: Command to run as user moblab.
        """
        command = "su - moblab -c '%s'" % command
        return self.run(command, **kwargs)


    def reboot(self, **dargs):
        """Reboot the Moblab Host and wait for its services to restart."""
        super(MoblabHost, self).reboot(**dargs)
        self.wait_afe_up()


    def wait_afe_up(self, timeout_min=5):
        """Wait till the AFE is up and loaded.

        Attempt to reach the Moblab's AFE and database through its RPC
        interface.

        @param timeout_min: Minutes to wait for the AFE to respond. Default is
                            5 minutes.

        @raises TimeoutException if AFE does not respond within the timeout.
        """
        # Use a new AFE object with a longer timeout to wait for the AFE to
        # load.
        afe = frontend_wrappers.RetryingAFE(timeout_min=timeout_min,
                                            server=self.hostname)
        # Verify the AFE can handle a simple request.
        afe.get_hosts()


    def find_and_add_duts(self):
        """Discover DUTs on the testing subnet and add them to the AFE.

        Runs 'arp -a' on the Moblab host and parses the output to discover DUTs
        and if they are not already in the AFE, adds them.
        """
        existing_hosts = [host.hostname for host in self.afe.get_hosts()]
        arp_command = self.run('arp -a')
        for line in arp_command.stdout.splitlines():
            match = re.match(SUBNET_DUT_SEARCH_RE, line)
            if match:
                dut_hostname = match.group('ip')
                if dut_hostname in existing_hosts:
                    break
                result = self.run_as_moblab('%s host create %s' %
                                            (ATEST_PATH, dut_hostname))
                logging.debug('atest host create output for host %s:\n%s',
                              dut_hostname, result.stdout)