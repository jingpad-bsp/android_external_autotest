# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib.cros import autoupdater
from autotest_lib.server import autoserv_parser
from autotest_lib.server import site_remote_power
from autotest_lib.server.hosts import base_classes


parser = autoserv_parser.autoserv_parser

# Time to wait for new kernel to be marked successful.
_KERNEL_UPDATE_TIMEOUT = 60

# Ephemeral file to indicate that an update has just occurred.
_JUST_UPDATED_FLAG = '/tmp/just_updated'


class ChromiumOSHost(base_classes.Host):
    """ChromiumOSHost is a special subclass of SSHHost that supports
    additional install methods.
    """
    def __initialize(self, hostname, *args, **dargs):
        """
        Construct a ChromiumOSHost object

        Args:
             hostname: network hostname or address of remote machine
        """
        super(ChromiumOSHost, self)._initialize(hostname, *args, **dargs)


    def machine_install(self, update_url=None, force_update=False):
        if parser.options.image:
            update_url = parser.options.image
        elif not update_url:
            raise autoupdater.ChromiumOSError(
                'Update failed. No update URL provided.')

        # Attempt to update the system.
        updater = autoupdater.ChromiumOSUpdater(update_url, host=self)
        if updater.run_update(force_update):
            # Figure out active and inactive kernel.
            active_kernel, inactive_kernel = updater.get_kernel_state()

            # Ensure inactive kernel has higher priority than active.
            if (updater.get_kernel_priority(inactive_kernel)
                    < updater.get_kernel_priority(active_kernel)):
                raise autoupdater.ChromiumOSError(
                    'Update failed. The priority of the inactive kernel'
                    ' partition is less than that of the active kernel'
                    ' partition.')

            # Updater has returned, successfully, reboot the host.
            self.reboot(timeout=60, wait=True)

            # Following the reboot, verify the correct version.
            updater.check_version()

            # Figure out newly active kernel.
            new_active_kernel, _ = updater.get_kernel_state()

            # Ensure that previously inactive kernel is now the active kernel.
            if new_active_kernel != inactive_kernel:
                raise autoupdater.ChromiumOSError(
                    'Update failed. New kernel partition is not active after'
                    ' boot.')

            # TODO(dalecurtis): Hack! Disable AU partition checks on ARM until
            # http://crosbug.com/15167 is fixed.
            if not 'ARM' in self.run('cat /proc/cpuinfo').stdout.strip():
                # Wait until tries == 0 and success, or until timeout.
                utils.poll_for_condition(
                    lambda: (updater.get_kernel_tries(new_active_kernel) == 0
                             and updater.get_kernel_success(new_active_kernel)),
                    exception=autoupdater.ChromiumOSError(
                        'Update failed. Timed out waiting for system to mark'
                        ' new kernel as successful.'),
                    timeout=_KERNEL_UPDATE_TIMEOUT, sleep_interval=5)

            # TODO(dalecurtis): Hack for R12 builds to make sure BVT runs of
            # platform_Shutdown pass correctly.
            if updater.update_version.startswith('0.12'):
                self.reboot(timeout=60, wait=True)

            # Mark host as recently updated. Hosts are rebooted at the end of
            # every test cycle which will remove the file.
            self.run('touch %s' % _JUST_UPDATED_FLAG)

        # Clean up any old autotest directories which may be lying around.
        for path in global_config.global_config.get_config_value(
                'AUTOSERV', 'client_autodir_paths', type=list):
            self.run('rm -rf ' + path)


    def has_just_updated(self):
        """Indicates whether the host was updated within this boot."""
        # Check for the existence of the just updated flag file.
        return self.run(
            '[ -f %s ] && echo T || echo F'
            % _JUST_UPDATED_FLAG).stdout.strip() == 'T'


    def cleanup(self):
        """Special cleanup method to make sure hosts always get power back."""
        super(ChromiumOSHost, self).cleanup()
        remote_power = site_remote_power.RemotePower(self.hostname)
        if remote_power:
            remote_power.set_power_on()


    def verify(self):
        """Override to ensure only our version of verify_software() is run."""
        self.verify_hardware()
        self.verify_connectivity()
        self.__verify_software()


    def __verify_software(self):
        """Ensure the stateful partition has space for Autotest and updates.

        Similar to what is done by AbstractSSH, except instead of checking the
        Autotest installation path, just check the stateful partition.

        Checking the stateful partition is preferable in case it has been wiped,
        resulting in an Autotest installation path which doesn't exist and isn't
        writable. We still want to pass verify in this state since the partition
        will be recovered with the next install.
        """
        super(ChromiumOSHost, self).verify_software()
        self.check_diskspace(
            '/mnt/stateful_partition',
            global_config.global_config.get_config_value(
                'SERVER', 'gb_diskspace_required', type=int,
                default=20))
