# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import common
import logging
import re
import tempfile
import time

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
MOBLAB_BOTO_LOCATION = '/home/moblab/.boto'
MOBLAB_AUTODIR = '/usr/local/autodir'
DHCPD_LEASE_FILE = '/var/lib/dhcp/dhcpd.leases'
MOBLAB_SERVICES = ['moblab-database-init',
                   'moblab-devserver-init',
                   'moblab-gsoffloader-init',
                   'moblab-gsoffloader_s-init']
MOBLAB_PROCESSES = ['apache2', 'dhcpd']
DUT_VERIFY_SLEEP_SECS = 5
DUT_VERIFY_TIMEOUT = 5 * 60


class MoblabHost(cros_host.CrosHost):
    """Moblab specific host class."""


    def _initialize(self, *args, **dargs):
        super(MoblabHost, self)._initialize(*args, **dargs)
        self.afe = frontend_wrappers.RetryingAFE(timeout_min=1,
                                                 server=self.hostname)
        # Clear the Moblab Image Storage so that staging an image is properly
        # tested.
        self.run('rm -rf %s/*' % MOBLAB_IMAGE_STORAGE)
        self._dhcpd_leasefile = None


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
        return MOBLAB_AUTODIR


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
        # Wake up devices listed by dhcp directly.
        leases = set(self.run('grep ^lease %s' % DHCPD_LEASE_FILE,
                              ignore_status=True).stdout.splitlines())
        for lease in leases:
            ip = re.match('lease (?P<ip>.*) {', lease).groups('ip')
            self.run('ping %s -w 1' % ip, ignore_status=True)
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


    def verify_software(self):
        """Verify working software on a Chrome OS system.

        Tests for the following conditions:
         1. All conditions tested by the parent version of this
            function.
         2. Ensures that Moblab services are running.
         3. Ensures that both DUTs successfully run Verify.

        """
        super(MoblabHost, self).verify_software()
        self._verify_moblab_services()
        self._verify_duts()


    def _verify_moblab_services(self):
        """Verify the required Moblab services are up and running.

        @raises AutoservError if any moblab service is not running.
        """
        for service in MOBLAB_SERVICES:
            if not self.upstart_status(service):
                raise error.AutoservError('Moblab service: %s is not running.'
                                          % service)
        for process in MOBLAB_PROCESSES:
            try:
                self.run('pgrep %s' % process)
            except error.AutoservRunError:
                raise error.AutoservError('Moblab process: %s is not running.'
                                          % process)


    def _verify_duts(self):
        """Verify the Moblab DUTs are up and running.

        @raises AutoservError if no DUTs are in the Ready State.
        """
        # Add the DUTs if they have not yet been added.
        self.find_and_add_duts()
        hosts = self.afe.reverify_hosts()
        logging.debug('DUTs scheduled for reverification: %s', hosts)
        # Wait till all pending special tasks are completed.
        total_time = 0
        while (self.afe.run('get_special_tasks', is_complete=False) and
               total_time < DUT_VERIFY_TIMEOUT):
            total_time = total_time + DUT_VERIFY_SLEEP_SECS
            time.sleep(DUT_VERIFY_SLEEP_SECS)
        if not self.afe.get_hosts(status='Ready'):
            for host in self.afe.get_hosts():
                logging.error('DUT: %s Status: %s', host, host.status)
            raise error.AutoservError('Moblab has 0 Ready DUTs')


    def check_device(self):
        """Moblab specific check_device.

        Runs after a repair method has been attempted:
        * Reboots the moblab to start its services.
        * Creates the autotest client directory in case powerwash was used to
          wipe stateful and repair.
        * Reinstall the dhcp lease file if it was preserved.
        """
        # Moblab requires a reboot to initialize it's services prior to
        # verification.
        self.reboot()
        # Stateful could have been wiped so setup an empty autotest client
        # directory.
        self.run('mkdir -p %s' % self.get_autodir(), ignore_status=True)
        # Restore the dhcpd lease file if it was backed up.
        # TODO (sbasi) - Currently this is required for repairs but may need
        # to be expanded to regular installs as well.
        if self._dhcpd_leasefile:
            self.send_file(self._dhcpd_leasefile.name, DHCPD_LEASE_FILE)
            self.run('chown dhcp:dhcp %s' % DHCPD_LEASE_FILE)
        super(MoblabHost, self).check_device()


    def repair_full(self):
        """Moblab specific repair_full.

        Preserves the dhcp lease file prior to repairing the device.
        """
        try:
            temp = tempfile.TemporaryFile()
            self.get_file(DHCPD_LEASE_FILE, temp.name)
            self._dhcpd_leasefile = temp
        except error.AutoservRunError:
            logging.debug('Failed to retrieve dhcpd lease file from host.')
        super(MoblabHost, self).repair_full()