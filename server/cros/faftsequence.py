# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ctypes
import logging
import os
import re
import subprocess
import time

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.server import hosts
from autotest_lib.server.cros import vboot_constants as vboot
from autotest_lib.server.cros.faft_checkers import FAFTCheckers
from autotest_lib.server.cros.faft_client_attribute import FAFTClientAttribute
from autotest_lib.server.cros.faft_delay_constants import FAFTDelayConstants
from autotest_lib.server.cros.servo import chrome_ec
from autotest_lib.server.cros.servo_test import ServoTest

class FAFTSequence(ServoTest):
    """
    The base class of Fully Automated Firmware Test Sequence.

    Many firmware tests require several reboot cycles and verify the resulted
    system states. To do that, an Autotest test case should detailly handle
    every action on each step. It makes the test case hard to read and many
    duplicated code. The base class FAFTSequence is to solve this problem.

    The actions of one reboot cycle is defined in a dict, namely FAFT_STEP.
    There are four functions in the FAFT_STEP dict:
        state_checker: a function to check the current is valid or not,
            returning True if valid, otherwise, False to break the whole
            test sequence.
        userspace_action: a function to describe the action ran in userspace.
        reboot_action: a function to do reboot, default: sync_and_warm_reboot.
        firmware_action: a function to describe the action ran after reboot.

    And configurations:
        install_deps_after_boot: if True, install the Autotest dependency after
             boot; otherwise, do nothing. It is for the cases of recovery mode
             test. The test boots a USB/SD image instead of an internal image.
             The previous installed Autotest dependency on the internal image
             is lost. So need to install it again.

    The default FAFT_STEP checks nothing in state_checker and does nothing in
    userspace_action and firmware_action. Its reboot_action is a hardware
    reboot. You can change the default FAFT_STEP by calling
    self.register_faft_template(FAFT_STEP).

    A FAFT test case consists of several FAFT_STEP's, namely FAFT_SEQUENCE.
    FAFT_SEQUENCE is an array of FAFT_STEP's. Any missing fields on FAFT_STEP
    fall back to default.

    In the run_once(), it should register and run FAFT_SEQUENCE like:
        def run_once(self):
            self.register_faft_sequence(FAFT_SEQUENCE)
            self.run_faft_sequnce()

    Note that in the last step, we only run state_checker. The
    userspace_action, reboot_action, and firmware_action are not executed.

    Attributes:
        _faft_template: The default FAFT_STEP of each step. The actions would
            be over-written if the registered FAFT_SEQUENCE is valid.
        _faft_sequence: The registered FAFT_SEQUENCE.
        _install_image_path: The URL or the path on the host to the Chrome OS
            test image to be installed.
        _firmware_update: Boolean. True if firmware update needed after
            installing the image.
    """
    version = 1

    # Mapping of partition number of kernel and rootfs.
    KERNEL_MAP = {'a':'2', 'b':'4', '2':'2', '4':'4', '3':'2', '5':'4'}
    ROOTFS_MAP = {'a':'3', 'b':'5', '2':'3', '4':'5', '3':'3', '5':'5'}
    OTHER_KERNEL_MAP = {'a':'4', 'b':'2', '2':'4', '4':'2', '3':'4', '5':'2'}
    OTHER_ROOTFS_MAP = {'a':'5', 'b':'3', '2':'5', '4':'3', '3':'5', '5':'3'}

    CHROMEOS_MAGIC = "CHROMEOS"
    CORRUPTED_MAGIC = "CORRUPTD"

    _ROOTFS_PARTITION_NUMBER = 3

    _HTTP_PREFIX = 'http://'
    _DEVSERVER_PORT = '8090'

    _faft_template = {}
    _faft_sequence = ()

    _install_image_path = None
    _firmware_update = False

    _backup_firmware_sha = ()


    # Class level variable, keep track the states of one time setup.
    # This variable is preserved across tests which inherit this class.
    _global_setup_done = {
        'gbb_flags': False,
        'reimage': False,
        'usb_check': False,
    }

    @classmethod
    def check_setup_done(cls, label):
        """Check if the given setup is done.

        Args:
          label: The label of the setup.
        """
        return cls._global_setup_done[label]


    @classmethod
    def mark_setup_done(cls, label):
        """Mark the given setup done.

        Args:
          label: The label of the setup.
        """
        cls._global_setup_done[label] = True


    @classmethod
    def unmark_setup_done(cls, label):
        """Mark the given setup not done.

        Args:
          label: The label of the setup.
        """
        cls._global_setup_done[label] = False


    def initialize(self, host, cmdline_args, use_pyauto=False, use_faft=False):
        # Parse arguments from command line
        args = {}
        self.power_control = host.POWER_CONTROL_RPM
        for arg in cmdline_args:
            match = re.search("^(\w+)=(.+)", arg)
            if match:
                args[match.group(1)] = match.group(2)
        if 'power_control' in args:
            self.power_control = args['power_control']
            if self.power_control not in host.POWER_CONTROL_VALID_ARGS:
                raise error.TestError('Valid values for --args=power_control '
                                      'are %s. But you entered wrong argument '
                                      'as "%s".'
                                       % (host.POWER_CONTROL_VALID_ARGS,
                                       self.power_control))
        if 'image' in args:
            self._install_image_path = args['image']
            logging.info('Install Chrome OS test image path: %s',
                    self._install_image_path)
        if 'firmware_update' in args and args['firmware_update'].lower() \
                not in ('0', 'false', 'no'):
            if self._install_image_path:
                self._firmware_update = True
                logging.info('Also update firmware after installing.')
            else:
                logging.warning('Firmware update will not not performed '
                                'since no image is specified.')

        super(FAFTSequence, self).initialize(host, cmdline_args, use_pyauto,
                use_faft)
        if use_faft:
            self.client_attr = FAFTClientAttribute(
                    self.faft_client.system.get_platform_name())
            self.delay = FAFTDelayConstants(
                    self.faft_client.system.get_platform_name())
            self.checkers = FAFTCheckers(self, self.faft_client)

            if self.client_attr.chrome_ec:
                self.ec = chrome_ec.ChromeEC(self.servo)

            if not self.client_attr.has_keyboard:
                # The environment variable USBKM232_UART_DEVICE should point
                # to the USB-KM232 UART device.
                if ('USBKM232_UART_DEVICE' not in os.environ or
                        not os.path.exists(os.environ['USBKM232_UART_DEVICE'])):
                    raise error.TestError('Must set a valid environment '
                            'variable USBKM232_UART_DEVICE.')

            # Setting up key matrix mapping
            self.servo.set_key_matrix(self.client_attr.key_matrix_layout)


    def setup(self, ec_wp=None):
        """Autotest setup function."""
        super(FAFTSequence, self).setup()
        self.register_faft_template({
            'state_checker': (None),
            'userspace_action': (None),
            'reboot_action': (self.sync_and_warm_reboot),
            'firmware_action': (None)
        })
        self.install_test_image(self._install_image_path, self._firmware_update)
        self.record_system_info()
        self.setup_gbb_flags()
        self.setup_ec_write_protect(ec_wp)


    def cleanup(self):
        """Autotest cleanup function."""
        self.restore_ec_write_protect()
        self._faft_sequence = ()
        self._faft_template = {}
        super(FAFTSequence, self).cleanup()


    def record_system_info(self):
        """Record some critical system info to the attr keyval.

        This info is used by generate_test_report and local_dash later.
        """
        self.write_attr_keyval({
            'fw_version': self.faft_client.ec.get_version(),
            'hwid': self.faft_client.system.get_crossystem_value('hwid'),
            'fwid': self.faft_client.system.get_crossystem_value('fwid'),
        })


    def invalidate_firmware_setup(self):
        """Invalidate all firmware related setup state.

        This method is called when the firmware is re-flashed. It resets all
        firmware related setup states so that the next test setup properly
        again.
        """
        self.unmark_setup_done('gbb_flags')


    def _retrieve_recovery_reason_from_trap(self):
        """Try to retrieve the recovery reason from a trapped recovery screen.

        Returns:
          The recovery_reason, 0 if any error.
        """
        recovery_reason = 0
        logging.info('Try to retrieve recovery reason...')
        if self.servo.get_usbkey_direction() == 'dut':
            self.wait_fw_screen_and_plug_usb()
        else:
            self.servo.switch_usbkey('dut')

        try:
            self.wait_for_client(install_deps=True)
            lines = self.faft_client.system.run_shell_command_get_output(
                        'crossystem recovery_reason')
            recovery_reason = int(lines[0])
            logging.info('Got the recovery reason %d.', recovery_reason)
        except AssertionError:
            logging.info('Failed to get the recovery reason.')
        return recovery_reason


    def _reset_client(self):
        """Reset client to a workable state.

        This method is called when the client is not responsive. It may be
        caused by the following cases:
          - halt on a firmware screen without timeout, e.g. REC_INSERT screen;
          - corrupted firmware;
          - corrutped OS image.
        """
        # DUT may halt on a firmware screen. Try cold reboot.
        logging.info('Try cold reboot...')
        self.cold_reboot()
        self.wait_for_client_offline()
        self.wait_dev_screen_and_ctrl_d()
        try:
            self.wait_for_client()
            return
        except AssertionError:
            pass

        # DUT may be broken by a corrupted firmware. Restore firmware.
        # We assume the recovery boot still works fine. Since the recovery
        # code is in RO region and all FAFT tests don't change the RO region
        # except GBB.
        if self.is_firmware_saved():
            self._ensure_client_in_recovery()
            logging.info('Try restore the original firmware...')
            if self.is_firmware_changed():
                try:
                    self.restore_firmware()
                    return
                except AssertionError:
                    logging.info('Restoring firmware doesn\'t help.')

        # DUT may be broken by a corrupted OS image. Restore OS image.
        self._ensure_client_in_recovery()
        logging.info('Try restore the OS image...')
        self.faft_client.system.run_shell_command('chromeos-install --yes')
        self.sync_and_warm_reboot()
        self.wait_for_client_offline()
        self.wait_dev_screen_and_ctrl_d()
        try:
            self.wait_for_client(install_deps=True)
            logging.info('Successfully restore OS image.')
            return
        except AssertionError:
            logging.info('Restoring OS image doesn\'t help.')


    def _ensure_client_in_recovery(self):
        """Ensure client in recovery boot; reboot into it if necessary.

        Raises:
            error.TestError: if failed to boot the USB image.
        """
        # DUT works fine and is already in recovery boot, done.
        if self._ping_test(self._client.ip, timeout=5):
            if self.checkers.crossystem_checker({'mainfw_type': 'recovery'}):
                return

        logging.info('Try boot into USB image...')
        self.servo.switch_usbkey('host')
        self.enable_rec_mode_and_reboot()
        self.wait_fw_screen_and_plug_usb()
        try:
            self.wait_for_client(install_deps=True)
        except AssertionError:
            raise error.TestError('Failed to boot the USB image.')


    def _restore_routine_from_timeout(self, next_step=None):
        """A routine to try to restore the system from a timeout error.

        This method is called when FAFT failed to connect DUT after reboot.

        Args:
          next_step: Optional, a FAFT_STEP dict of the next step, which is used
                     for diagnostic.

        Raises:
          error.TestFail: This exception is already raised, with a decription
                          why it failed.
        """
        next_checker_matched = False
        if next_step is not None:
            next_test = {}
            next_test.update(self._faft_template)
            next_test.update(next_step)

        # TODO(waihong@chromium.org): Implement replugging the Ethernet to
        # identify if it is a network flaky.

        recovery_reason = self._retrieve_recovery_reason_from_trap()
        if next_step is not None and recovery_reason:
            if self._call_action(next_test['state_checker']):
                # Repluging the USB can pass the state_checker of the next step,
                # meaning that the firmware failed to boot into USB directly.
                next_checker_matched = True

        # Reset client to a workable state.
        self._reset_client()

        # Raise the proper TestFail exception.
        if next_checker_matched:
            raise error.TestFail('Firmware failed to auto-boot USB in the '
                                 'recovery boot (reason: %d)' % recovery_reason)
        elif recovery_reason:
            raise error.TestFail('Trapped in the recovery screen (reason: %d) '
                                 'and timed out' % recovery_reason)
        else:
            raise error.TestFail('Timed out waiting for DUT reboot')


    def assert_test_image_in_usb_disk(self, usb_dev=None, install_shim=False):
        """Assert an USB disk plugged-in on servo and a test image inside.

        Args:
          usb_dev: A string of USB stick path on the host, like '/dev/sdc'.
                   If None, it is detected automatically.
          install_shim: True to verify an install shim instead of a test image.

        Raises:
          error.TestError: if USB disk not detected or not a test (install shim)
                           image.
        """
        if self.check_setup_done('usb_check'):
            return
        if usb_dev:
            assert self.servo.get_usbkey_direction() == 'host'
        else:
            self.servo.switch_usbkey('host')
            usb_dev = self.servo.probe_host_usb_dev()
            if not usb_dev:
                raise error.TestError(
                        'An USB disk should be plugged in the servo board.')

        rootfs = '%s%s' % (usb_dev, self._ROOTFS_PARTITION_NUMBER)
        logging.info('usb dev is %s', usb_dev)
        tmpd = self.servo.system_output('mktemp -d -t usbcheck.XXXX')
        self.servo.system('mount -o ro %s %s' % (rootfs, tmpd))

        if install_shim:
            dir_list = self.servo.system_output('ls -a %s' %
                                                os.path.join(tmpd, 'root'))
            check_passed = '.factory_installer' in dir_list
        else:
            check_passed = self.servo.system_output(
                'grep -i "CHROMEOS_RELEASE_DESCRIPTION=.*test" %s' %
                os.path.join(tmpd, 'etc/lsb-release'),
                ignore_status=True)
        for cmd in ('umount %s' % rootfs, 'sync', 'rm -rf %s' % tmpd):
            self.servo.system(cmd)

        if not check_passed:
            raise error.TestError(
                'No Chrome OS %s found on the USB flash plugged into servo' %
                'install shim' if install_shim else 'test')

        self.mark_setup_done('usb_check')


    def setup_usbkey(self, usbkey, host=None, install_shim=False):
        """Setup the USB disk for the test.

        It checks the setup of USB disk and a valid ChromeOS test image inside.
        It also muxes the USB disk to either the host or DUT by request.

        Args:
          usbkey: True if the USB disk is required for the test, False if not
                  required.
          host: Optional, True to mux the USB disk to host, False to mux it
                to DUT, default to do nothing.
          install_shim: True to verify an install shim instead of a test image.
        """
        if usbkey:
            self.assert_test_image_in_usb_disk(install_shim=install_shim)
        elif host is None:
            # USB disk is not required for the test. Better to mux it to host.
            host = True

        if host is True:
            self.servo.switch_usbkey('host')
        elif host is False:
            self.servo.switch_usbkey('dut')


    def get_server_address(self):
        """Get the server address seen from the client.

        Returns:
          A string of the server address.
        """
        r = self.faft_client.system.run_shell_command_get_output(
                "echo $SSH_CLIENT")
        return r[0].split()[0]


    def install_test_image(self, image_path=None, firmware_update=False):
        """Install the test image specied by the path onto the USB and DUT disk.

        The method first copies the image to USB disk and reboots into it via
        recovery mode. Then runs 'chromeos-install' (and possible
        chromeos-firmwareupdate') to install it to DUT disk.

        Sample command line:

        run_remote_tests.sh --servo --board=daisy --remote=w.x.y.z \
            --args="image=/tmp/chromiumos_test_image.bin firmware_update=True" \
            server/site_tests/firmware_XXXX/control

        This test requires an automated recovery to occur while simulating
        inserting and removing the usb key from the servo. To allow this the
        following hardware setup is required:
        1. servo2 board connected via servoflex.
        2. USB key inserted in the servo2.
        3. servo2 connected to the dut via dut_hub_in in the usb 2.0 slot.
        4. network connected via usb dongle in the dut in usb 3.0 slot.

        Args:
            image_path: An URL or a path on the host to the test image.
            firmware_update: Also update the firmware after installing.

        Raises:
          error.TestError: If devserver failed to start.
        """
        if not image_path:
            return

        if self.check_setup_done('reimage'):
            return

        if image_path.startswith(self._HTTP_PREFIX):
            # TODO(waihong@chromium.org): Add the check of the URL to ensure
            # it is a test image.
            devserver = None
            image_url = image_path
        elif self.servo.is_localhost():
            # If servod is localhost, i.e. both servod and FAFT see the same
            # file system, do nothing.
            devserver = None
            image_url = image_path
        else:
            image_dir, image_base = os.path.split(image_path)
            logging.info('Starting devserver to serve the image...')
            # The following stdout and stderr arguments should not be None,
            # even we don't use them. Otherwise, the socket of devserve is
            # created as fd 1 (as no stdout) but it still thinks stdout is fd
            # 1 and dump the log to the socket. Wrong HTTP protocol happens.
            devserver = subprocess.Popen(['/usr/lib/devserver/devserver.py',
                        '--archive_dir=%s' % image_dir,
                        '--port=%s' % self._DEVSERVER_PORT],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE)
            image_url = '%s%s:%s/static/archive/%s' % (
                        self._HTTP_PREFIX,
                        self.get_server_address(),
                        self._DEVSERVER_PORT,
                        image_base)

            # Wait devserver startup completely
            time.sleep(self.delay.devserver)
            # devserver is a service running forever. If it is terminated,
            # some error does happen.
            if devserver.poll():
                raise error.TestError('Starting devserver failed, '
                                      'returning %d.' % devserver.returncode)

        logging.info('Ask Servo to install the image from %s', image_url)
        self.servo.image_to_servo_usb(image_url)

        self.assert_test_image_in_usb_disk()

        if devserver and devserver.poll() is None:
            logging.info('Shutting down devserver...')
            devserver.terminate()

        # DUT is powered off while imaging servo USB.
        # Now turn it on.
        self.servo.power_short_press()
        self.wait_for_client()
        self.servo.switch_usbkey('dut')

        install_cmd = 'chromeos-install --yes'
        if firmware_update:
            install_cmd += ' && chromeos-firmwareupdate --mode recovery'
            self.backup_firmware()

        self.register_faft_sequence((
            {   # Step 1, request recovery boot
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_type': ('developer', 'normal'),
                }),
                'userspace_action': (
                    self.faft_client.system.request_recovery_boot),
                'firmware_action': self.wait_fw_screen_and_plug_usb,
                'install_deps_after_boot': True,
            },
            {   # Step 2, expected recovery boot
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_type': 'recovery',
                    'recovery_reason' : vboot.RECOVERY_REASON['US_TEST'],
                }),
                'userspace_action': (self.faft_client.system.run_shell_command,
                                     install_cmd),
                'reboot_action': self.cold_reboot,
                'install_deps_after_boot': True,
            },
            {   # Step 3, expected normal or developer boot (not recovery)
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_type': ('developer', 'normal')
                }),
            },
        ))
        self.run_faft_sequence()

        if firmware_update:
            self.clear_saved_firmware()

        # 'Unplug' any USB keys in the servo from the dut.
        self.servo.switch_usbkey('host')
        # Mark usb_check done so it won't check a test image in USB anymore.
        self.mark_setup_done('usb_check')
        self.mark_setup_done('reimage')


    def clear_set_gbb_flags(self, clear_mask, set_mask):
        """Clear and set the GBB flags in the current flashrom.

        Args:
          clear_mask: A mask of flags to be cleared.
          set_mask: A mask of flags to be set.
        """
        gbb_flags = self.faft_client.bios.get_gbb_flags()
        new_flags = gbb_flags & ctypes.c_uint32(~clear_mask).value | set_mask

        if (gbb_flags != new_flags):
            logging.info('Change the GBB flags from 0x%x to 0x%x.',
                         gbb_flags, new_flags)
            self.faft_client.system.run_shell_command(
                    '/usr/share/vboot/bin/set_gbb_flags.sh 0x%x' % new_flags)
            self.faft_client.bios.reload()
            # If changing FORCE_DEV_SWITCH_ON flag, reboot to get a clear state
            if ((gbb_flags ^ new_flags) & vboot.GBB_FLAG_FORCE_DEV_SWITCH_ON):
                self.run_faft_step({
                    'firmware_action': self.wait_dev_screen_and_ctrl_d,
                })


    def check_ec_capability(self, required_cap=None, suppress_warning=False):
        """Check if current platform has required EC capabilities.

        Args:
          required_cap: A list containing required EC capabilities. Pass in
            None to only check for presence of Chrome EC.
          suppress_warning: True to suppress any warning messages.

        Returns:
          True if requirements are met. Otherwise, False.
        """
        if not self.client_attr.chrome_ec:
            if not suppress_warning:
                logging.warn('Requires Chrome EC to run this test.')
            return False

        if not required_cap:
            return True

        for cap in required_cap:
            if cap not in self.client_attr.ec_capability:
                if not suppress_warning:
                    logging.warn('Requires EC capability "%s" to run this '
                                 'test.', cap)
                return False

        return True


    def check_root_part_on_non_recovery(self, part):
        """Check the partition number of root device and on normal/dev boot.

        Returns:
            True if the root device matched and on normal/dev boot;
            otherwise, False.
        """
        return self.checkers.root_part_checker(part) and \
                self.checkers.crossystem_checker({
                    'mainfw_type': ('normal', 'developer'),
                })


    def _join_part(self, dev, part):
        """Return a concatenated string of device and partition number.

        Args:
          dev: A string of device, e.g.'/dev/sda'.
          part: A string of partition number, e.g.'3'.

        Returns:
          A concatenated string of device and partition number, e.g.'/dev/sda3'.

        >>> seq = FAFTSequence()
        >>> seq._join_part('/dev/sda', '3')
        '/dev/sda3'
        >>> seq._join_part('/dev/mmcblk0', '2')
        '/dev/mmcblk0p2'
        """
        if 'mmcblk' in dev:
            return dev + 'p' + part
        else:
            return dev + part


    def copy_kernel_and_rootfs(self, from_part, to_part):
        """Copy kernel and rootfs from from_part to to_part.

        Args:
          from_part: A string of partition number to be copied from.
          to_part: A string of partition number to be copied to.
        """
        root_dev = self.faft_client.system.get_root_dev()
        logging.info('Copying kernel from %s to %s. Please wait...',
                     from_part, to_part)
        self.faft_client.system.run_shell_command('dd if=%s of=%s bs=4M' %
                (self._join_part(root_dev, self.KERNEL_MAP[from_part]),
                 self._join_part(root_dev, self.KERNEL_MAP[to_part])))
        logging.info('Copying rootfs from %s to %s. Please wait...',
                     from_part, to_part)
        self.faft_client.system.run_shell_command('dd if=%s of=%s bs=4M' %
                (self._join_part(root_dev, self.ROOTFS_MAP[from_part]),
                 self._join_part(root_dev, self.ROOTFS_MAP[to_part])))


    def ensure_kernel_boot(self, part):
        """Ensure the request kernel boot.

        If not, it duplicates the current kernel to the requested kernel
        and sets the requested higher priority to ensure it boot.

        Args:
          part: A string of kernel partition number or 'a'/'b'.
        """
        if not self.checkers.root_part_checker(part):
            if self.faft_client.kernel.diff_a_b():
                self.copy_kernel_and_rootfs(
                        from_part=self.OTHER_KERNEL_MAP[part],
                        to_part=part)
            self.run_faft_step({
                'userspace_action': (self.reset_and_prioritize_kernel, part),
            })


    def set_hardware_write_protect(self, enable):
        """Set hardware write protect pin.

        Args:
          enable: True if asserting write protect pin. Otherwise, False.
        """
        self.servo.set('fw_wp_vref', self.client_attr.wp_voltage)
        self.servo.set('fw_wp_en', 'on')
        self.servo.set('fw_wp', 'on' if enable else 'off')


    def set_ec_write_protect_and_reboot(self, enable):
        """Set EC write protect status and reboot to take effect.

        The write protect state is only activated if both hardware write
        protect pin is asserted and software write protect flag is set.
        This method asserts/deasserts hardware write protect pin first, and
        set corresponding EC software write protect flag.

        If the device uses non-Chrome EC, set the software write protect via
        flashrom.

        If the device uses Chrome EC, a reboot is required for write protect
        to take effect. Since the software write protect flag cannot be unset
        if hardware write protect pin is asserted, we need to deasserted the
        pin first if we are deactivating write protect. Similarly, a reboot
        is required before we can modify the software flag.

        Args:
          enable: True if activating EC write protect. Otherwise, False.
        """
        self.set_hardware_write_protect(enable)
        if self.client_attr.chrome_ec:
            self.set_chrome_ec_write_protect_and_reboot(enable)
        else:
            self.faft_client.ec.set_write_protect(enable)
            self.sync_and_warm_reboot()


    def set_chrome_ec_write_protect_and_reboot(self, enable):
        """Set Chrome EC write protect status and reboot to take effect.

        Args:
          enable: True if activating EC write protect. Otherwise, False.
        """
        if enable:
            # Set write protect flag and reboot to take effect.
            self.ec.set_flash_write_protect(enable)
            self.sync_and_ec_reboot()
        else:
            # Reboot after deasserting hardware write protect pin to deactivate
            # write protect. And then remove software write protect flag.
            self.sync_and_ec_reboot()
            self.ec.set_flash_write_protect(enable)


    def setup_ec_write_protect(self, ec_wp):
        """Setup for EC write-protection.

        It makes sure the EC in the requested write-protection state. If not, it
        flips the state. Flipping the write-protection requires DUT reboot.

        Args:
          ec_wp: True to request EC write-protected; False to request EC not
                 write-protected; None to do nothing.
        """
        if ec_wp is None:
            self._old_ec_wp = None
            return
        self._old_ec_wp = self.checkers.crossystem_checker({'wpsw_boot': '1'})
        if ec_wp != self._old_ec_wp:
            logging.info('The test required EC is %swrite-protected. Reboot '
                         'and flip the state.', '' if ec_wp else 'not ')
            self.run_faft_step({
                'reboot_action': (self.set_ec_write_protect_and_reboot, ec_wp),
                'firmware_action': self.wait_dev_screen_and_ctrl_d,
            })


    def restore_ec_write_protect(self):
        """Restore the original EC write-protection."""
        if self._old_ec_wp is None:
            return
        if not self.checkers.crossystem_checker(
                {'wpsw_boot': '1' if self._old_ec_wp else '0'}):
            logging.info('Restore the original EC write protection and reboot.')
            self.run_faft_step({
                'reboot_action': (self.set_ec_write_protect_and_reboot,
                                  self._old_ec_wp),
                'firmware_action': self.wait_dev_screen_and_ctrl_d,
            })


    def press_ctrl_d(self):
        """Send Ctrl-D key to DUT."""
        if not self.client_attr.has_keyboard:
            logging.info('Running usbkm232-ctrld...')
            os.system('usbkm232-ctrld')
        else:
            self.servo.ctrl_d()


    def press_ctrl_u(self):
        """Send Ctrl-U key to DUT.

        Raises:
          error.TestError: if a non-Chrome EC device or no Ctrl-U command given
                           on a no-build-in-keyboard device.
        """
        if not self.client_attr.has_keyboard:
            logging.info('Running usbkm232-ctrlu...')
            os.system('usbkm232-ctrlu')
        elif self.check_ec_capability(['keyboard'], suppress_warning=True):
            self.ec.key_down('<ctrl_l>')
            self.ec.key_down('u')
            self.ec.key_up('u')
            self.ec.key_up('<ctrl_l>')
        elif self.client_attr.has_keyboard:
            raise error.TestError(
                    "Can't send Ctrl-U to DUT without using Chrome EC.")
        else:
            raise error.TestError(
                    "Should specify the ctrl_u_cmd argument.")


    def press_enter(self, press_secs=None):
        """Send Enter key to DUT."""
        if not self.client_attr.has_keyboard:
            logging.info('Running usbkm232-enter...')
            os.system('usbkm232-enter')
        else:
            self.servo.enter_key(press_secs)


    def wait_dev_screen_and_ctrl_d(self):
        """Wait for firmware warning screen and press Ctrl-D."""
        time.sleep(self.delay.dev_screen)
        self.press_ctrl_d()


    def wait_fw_screen_and_ctrl_d(self):
        """Wait for firmware warning screen and press Ctrl-D."""
        time.sleep(self.delay.firmware_screen)
        self.press_ctrl_d()


    def wait_fw_screen_and_ctrl_u(self):
        """Wait for firmware warning screen and press Ctrl-U."""
        time.sleep(self.delay.firmware_screen)
        self.press_ctrl_u()


    def wait_fw_screen_and_trigger_recovery(self, need_dev_transition=False):
        """Wait for firmware warning screen and trigger recovery boot."""
        time.sleep(self.delay.firmware_screen)

        # Pressing Enter for too long triggers a second key press.
        # Let's press it without delay
        self.press_enter(press_secs=0)

        # For Alex/ZGB, there is a dev warning screen in text mode.
        # Skip it by pressing Ctrl-D.
        if need_dev_transition:
            time.sleep(self.delay.legacy_text_screen)
            self.press_ctrl_d()


    def wait_fw_screen_and_unplug_usb(self):
        """Wait for firmware warning screen and then unplug the servo USB."""
        time.sleep(self.delay.load_usb)
        self.servo.switch_usbkey('host')
        time.sleep(self.delay.between_usb_plug)


    def wait_fw_screen_and_plug_usb(self):
        """Wait for firmware warning screen and then unplug and plug the USB."""
        self.wait_fw_screen_and_unplug_usb()
        self.servo.switch_usbkey('dut')


    def wait_fw_screen_and_press_power(self):
        """Wait for firmware warning screen and press power button."""
        time.sleep(self.delay.firmware_screen)
        # While the firmware screen, the power button probing loop sleeps
        # 0.25 second on every scan. Use the normal delay (1.2 second) for
        # power press.
        self.servo.power_normal_press()


    def wait_longer_fw_screen_and_press_power(self):
        """Wait for firmware screen without timeout and press power button."""
        time.sleep(self.delay.dev_screen_timeout)
        self.wait_fw_screen_and_press_power()


    def wait_fw_screen_and_close_lid(self):
        """Wait for firmware warning screen and close lid."""
        time.sleep(self.delay.firmware_screen)
        self.servo.lid_close()


    def wait_longer_fw_screen_and_close_lid(self):
        """Wait for firmware screen without timeout and close lid."""
        time.sleep(self.delay.firmware_screen)
        self.wait_fw_screen_and_close_lid()


    def setup_gbb_flags(self):
        """Setup the GBB flags for FAFT test."""
        if self.client_attr.gbb_version < 1.1:
            logging.info('Skip modifying GBB on versions older than 1.1.')
            return

        if self.check_setup_done('gbb_flags'):
            return

        logging.info('Set proper GBB flags for test.')
        self.clear_set_gbb_flags(vboot.GBB_FLAG_DEV_SCREEN_SHORT_DELAY |
                                 vboot.GBB_FLAG_FORCE_DEV_SWITCH_ON |
                                 vboot.GBB_FLAG_FORCE_DEV_BOOT_USB |
                                 vboot.GBB_FLAG_DISABLE_FW_ROLLBACK_CHECK,
                                 vboot.GBB_FLAG_ENTER_TRIGGERS_TONORM |
                                 vboot.GBB_FLAG_FAFT_KEY_OVERIDE)
        self.mark_setup_done('gbb_flags')


    def setup_tried_fwb(self, tried_fwb):
        """Setup for fw B tried state.

        It makes sure the system in the requested fw B tried state. If not, it
        tries to do so.

        Args:
          tried_fwb: True if requested in tried_fwb=1; False if tried_fwb=0.
        """
        if tried_fwb:
            if not self.checkers.crossystem_checker({'tried_fwb': '1'}):
                logging.info(
                    'Firmware is not booted with tried_fwb. Reboot into it.')
                self.run_faft_step({
                    'userspace_action': self.faft_client.system.set_try_fw_b,
                })
        else:
            if not self.checkers.crossystem_checker({'tried_fwb': '0'}):
                logging.info(
                    'Firmware is booted with tried_fwb. Reboot to clear.')
                self.run_faft_step({})


    def power_on(self):
        """Switch DUT AC power on."""
        self._client.power_on(self.power_control)


    def power_off(self):
        """Switch DUT AC power off."""
        self._client.power_off(self.power_control)


    def power_cycle(self):
        """Power cycle DUT AC power."""
        self._client.power_cycle(self.power_control)


    def enable_rec_mode_and_reboot(self):
        """Switch to rec mode and reboot.

        This method emulates the behavior of the old physical recovery switch,
        i.e. switch ON + reboot + switch OFF, and the new keyboard controlled
        recovery mode, i.e. just press Power + Esc + Refresh.
        """
        if self.client_attr.chrome_ec:
            # Reset twice to emulate a long recovery-key-combo hold.
            cold_reset_num = 2 if self.client_attr.long_rec_combo else 1
            for i in range(cold_reset_num):
                if i:
                    time.sleep(self.delay.ec_boot_to_console)
                # Cold reset to clear EC_IN_RW signal
                self.servo.set('cold_reset', 'on')
                time.sleep(self.delay.hold_cold_reset)
                self.servo.set('cold_reset', 'off')
            time.sleep(self.delay.ec_boot_to_console)
            self.ec.reboot("ap-off")
            time.sleep(self.delay.ec_boot_to_console)
            self.ec.set_hostevent(chrome_ec.HOSTEVENT_KEYBOARD_RECOVERY)
            self.servo.power_short_press()
        elif self.client_attr.broken_rec_mode:
            self.power_cycle()
            logging.info('Booting to recovery mode.')
            self.servo.custom_recovery_mode()
        else:
            self.servo.enable_recovery_mode()
            self.cold_reboot()
            time.sleep(self.delay.ec_boot_to_console)
            self.servo.disable_recovery_mode()


    def enable_dev_mode_and_reboot(self):
        """Switch to developer mode and reboot."""
        if self.client_attr.keyboard_dev:
            self.enable_keyboard_dev_mode()
        else:
            self.servo.enable_development_mode()
            self.faft_client.system.run_shell_command(
                    'chromeos-firmwareupdate --mode todev && reboot')


    def enable_normal_mode_and_reboot(self):
        """Switch to normal mode and reboot."""
        if self.client_attr.keyboard_dev:
            self.disable_keyboard_dev_mode()
        else:
            self.servo.disable_development_mode()
            self.faft_client.system.run_shell_command(
                    'chromeos-firmwareupdate --mode tonormal && reboot')


    def wait_fw_screen_and_switch_keyboard_dev_mode(self, dev):
        """Wait for firmware screen and then switch into or out of dev mode.

        Args:
          dev: True if switching into dev mode. Otherwise, False.
        """
        time.sleep(self.delay.firmware_screen)
        if dev:
            self.press_ctrl_d()
        else:
            self.press_enter()
        time.sleep(self.delay.confirm_screen)
        self.press_enter()


    def enable_keyboard_dev_mode(self):
        logging.info("Enabling keyboard controlled developer mode")
        # Plug out USB disk for preventing recovery boot without warning
        self.servo.switch_usbkey('host')
        # Rebooting EC with rec mode on. Should power on AP.
        self.enable_rec_mode_and_reboot()
        self.wait_for_client_offline()
        self.wait_fw_screen_and_switch_keyboard_dev_mode(dev=True)

        # TODO (crosbug.com/p/16231) remove this conditional completely if/when
        # issue is resolved.
        if self.client_attr.platform == 'Parrot':
            self.wait_for_client_offline()
            self.cold_reboot()


    def disable_keyboard_dev_mode(self):
        logging.info("Disabling keyboard controlled developer mode")
        if (not self.client_attr.chrome_ec and
            not self.client_attr.broken_rec_mode):
            self.servo.disable_recovery_mode()
        self.cold_reboot()
        self.wait_for_client_offline()
        self.wait_fw_screen_and_switch_keyboard_dev_mode(dev=False)


    def setup_dev_mode(self, dev_mode):
        """Setup for development mode.

        It makes sure the system in the requested normal/dev mode. If not, it
        tries to do so.

        Args:
          dev_mode: True if requested in dev mode; False if normal mode.
        """
        # Change the default firmware_action for dev mode passing the fw screen.
        self.register_faft_template({
            'firmware_action': (self.wait_dev_screen_and_ctrl_d if dev_mode
                                else None),
        })
        if dev_mode:
            if (not self.client_attr.keyboard_dev and
                not self.checkers.crossystem_checker({'devsw_cur': '1'})):
                logging.info('Dev switch is not on. Now switch it on.')
                self.servo.enable_development_mode()
            if not self.checkers.crossystem_checker({'devsw_boot': '1',
                    'mainfw_type': 'developer'}):
                logging.info('System is not in dev mode. Reboot into it.')
                self.run_faft_step({
                    'userspace_action': None if self.client_attr.keyboard_dev
                        else (self.faft_client.system.run_shell_command,
                        'chromeos-firmwareupdate --mode todev && reboot'),
                    'reboot_action': self.enable_keyboard_dev_mode if
                        self.client_attr.keyboard_dev else None,
                })
        else:
            if (not self.client_attr.keyboard_dev and
                not self.checkers.crossystem_checker({'devsw_cur': '0'})):
                logging.info('Dev switch is not off. Now switch it off.')
                self.servo.disable_development_mode()
            if not self.checkers.crossystem_checker({'devsw_boot': '0',
                    'mainfw_type': 'normal'}):
                logging.info('System is not in normal mode. Reboot into it.')
                self.run_faft_step({
                    'userspace_action': None if self.client_attr.keyboard_dev
                        else (self.faft_client.system.run_shell_command,
                        'chromeos-firmwareupdate --mode tonormal && reboot'),
                    'reboot_action': self.disable_keyboard_dev_mode if
                        self.client_attr.keyboard_dev else None,
                })


    def setup_rw_boot(self, section='a'):
        """Make sure firmware is in RW-boot mode.

        If the given firmware section is in RO-boot mode, turn off the RO-boot
        flag and reboot DUT into RW-boot mode.

        Args:
          section: A firmware section, either 'a' or 'b'.
        """
        flags = self.faft_client.bios.get_preamble_flags(section)
        if flags & vboot.PREAMBLE_USE_RO_NORMAL:
            flags = flags ^ vboot.PREAMBLE_USE_RO_NORMAL
            self.run_faft_step({
                'userspace_action': (self.faft_client.bios.set_preamble_flags,
                    (section, flags))
            })


    def setup_kernel(self, part):
        """Setup for kernel test.

        It makes sure both kernel A and B bootable and the current boot is
        the requested kernel part.

        Args:
          part: A string of kernel partition number or 'a'/'b'.
        """
        self.ensure_kernel_boot(part)
        if self.faft_client.kernel.diff_a_b():
            self.copy_kernel_and_rootfs(from_part=part,
                                        to_part=self.OTHER_KERNEL_MAP[part])
        self.reset_and_prioritize_kernel(part)


    def reset_and_prioritize_kernel(self, part):
        """Make the requested partition highest priority.

        This function also reset kerenl A and B to bootable.

        Args:
          part: A string of partition number to be prioritized.
        """
        root_dev = self.faft_client.system.get_root_dev()
        # Reset kernel A and B to bootable.
        self.faft_client.system.run_shell_command(
            'cgpt add -i%s -P1 -S1 -T0 %s' % (self.KERNEL_MAP['a'], root_dev))
        self.faft_client.system.run_shell_command(
            'cgpt add -i%s -P1 -S1 -T0 %s' % (self.KERNEL_MAP['b'], root_dev))
        # Set kernel part highest priority.
        self.faft_client.system.run_shell_command('cgpt prioritize -i%s %s' %
                (self.KERNEL_MAP[part], root_dev))
        # Safer to sync and wait until the cgpt status written to the disk.
        self.faft_client.system.run_shell_command('sync')
        time.sleep(self.delay.sync)


    def warm_reboot(self):
        """Request a warm reboot.

        A wrapper for underlying servo warm reset.
        """
        # Use cold reset if the warm reset is broken.
        if self.client_attr.broken_warm_reset:
            logging.info('broken_warm_reset is True. Cold rebooting instead.')
            self.cold_reboot()
        else:
            self.servo.get_power_state_controller().warm_reset()


    def cold_reboot(self):
        """Request a cold reboot.

        A wrapper for underlying servo cold reset.
        """
        if self.client_attr.broken_warm_reset:
            self.servo.set('pwr_button', 'press')
            self.servo.set('cold_reset', 'on')
            self.servo.set('cold_reset', 'off')
            time.sleep(self.delay.ec_boot_to_pwr_button)
            self.servo.set('pwr_button', 'release')
        else:
            self.servo.get_power_state_controller().cold_reset()


    def sync_and_warm_reboot(self):
        """Request the client sync and do a warm reboot.

        This is the default reboot action on FAFT.
        """
        self.faft_client.system.run_shell_command('sync')
        time.sleep(self.delay.sync)
        self.warm_reboot()


    def sync_and_cold_reboot(self):
        """Request the client sync and do a cold reboot.

        This reboot action is used to reset EC for recovery mode.
        """
        self.faft_client.system.run_shell_command('sync')
        time.sleep(self.delay.sync)
        self.cold_reboot()


    def sync_and_ec_reboot(self, flags=''):
        """Request the client sync and do a EC triggered reboot.

        Args:
          flags: Optional, a space-separated string of flags passed to EC
                 reboot command, including:
                   default: EC soft reboot;
                   'hard': EC cold/hard reboot.
        """
        self.faft_client.system.run_shell_command('sync')
        time.sleep(self.delay.sync)
        self.ec.reboot(flags)
        time.sleep(self.delay.ec_boot_to_console)
        self.check_lid_and_power_on()


    def reboot_with_factory_install_shim(self):
        """Request reboot with factory install shim to reset TPM.

        Factory install shim requires dev mode enabled. So this method switches
        firmware to dev mode first and reboot. The client uses factory install
        shim to reset TPM values.
        """
        # Unplug USB first to avoid the complicated USB autoboot cases.
        self.servo.switch_usbkey('host')
        is_dev = self.checkers.crossystem_checker({'devsw_boot': '1'})
        if not is_dev:
            self.enable_dev_mode_and_reboot()
        time.sleep(self.delay.sync)
        self.enable_rec_mode_and_reboot()
        self.wait_fw_screen_and_plug_usb()
        time.sleep(self.delay.install_shim_done)
        self.warm_reboot()


    def full_power_off_and_on(self):
        """Shutdown the device by pressing power button and power on again."""
        # Press power button to trigger Chrome OS normal shutdown process.
        # We use a customized delay since the normal-press 1.2s is not enough.
        self.servo.power_key(self.delay.hold_pwr_button)
        time.sleep(self.delay.shutdown)
        # Short press power button to boot DUT again.
        self.servo.power_short_press()


    def check_lid_and_power_on(self):
        """
        On devices with EC software sync, system powers on after EC reboots if
        lid is open. Otherwise, the EC shuts down CPU after about 3 seconds.
        This method checks lid switch state and presses power button if
        necessary.
        """
        if self.servo.get("lid_open") == "no":
            time.sleep(self.delay.software_sync)
            self.servo.power_short_press()


    def _modify_usb_kernel(self, usb_dev, from_magic, to_magic):
        """Modify the kernel header magic in USB stick.

        The kernel header magic is the first 8-byte of kernel partition.
        We modify it to make it fail on kernel verification check.

        Args:
          usb_dev: A string of USB stick path on the host, like '/dev/sdc'.
          from_magic: A string of magic which we change it from.
          to_magic: A string of magic which we change it to.

        Raises:
          error.TestError: if failed to change magic.
        """
        assert len(from_magic) == 8
        assert len(to_magic) == 8
        # USB image only contains one kernel.
        kernel_part = self._join_part(usb_dev, self.KERNEL_MAP['a'])
        read_cmd = "sudo dd if=%s bs=8 count=1 2>/dev/null" % kernel_part
        current_magic = self.servo.system_output(read_cmd)
        if current_magic == to_magic:
            logging.info("The kernel magic is already %s.", current_magic)
            return
        if current_magic != from_magic:
            raise error.TestError("Invalid kernel image on USB: wrong magic.")

        logging.info('Modify the kernel magic in USB, from %s to %s.',
                     from_magic, to_magic)
        write_cmd = ("echo -n '%s' | sudo dd of=%s oflag=sync conv=notrunc "
                     " 2>/dev/null" % (to_magic, kernel_part))
        self.servo.system(write_cmd)

        if self.servo.system_output(read_cmd) != to_magic:
            raise error.TestError("Failed to write new magic.")


    def corrupt_usb_kernel(self, usb_dev):
        """Corrupt USB kernel by modifying its magic from CHROMEOS to CORRUPTD.

        Args:
          usb_dev: A string of USB stick path on the host, like '/dev/sdc'.
        """
        self._modify_usb_kernel(usb_dev, self.CHROMEOS_MAGIC,
                                self.CORRUPTED_MAGIC)


    def restore_usb_kernel(self, usb_dev):
        """Restore USB kernel by modifying its magic from CORRUPTD to CHROMEOS.

        Args:
          usb_dev: A string of USB stick path on the host, like '/dev/sdc'.
        """
        self._modify_usb_kernel(usb_dev, self.CORRUPTED_MAGIC,
                                self.CHROMEOS_MAGIC)


    def _call_action(self, action_tuple, check_status=False):
        """Call the action function with/without arguments.

        Args:
          action_tuple: A function, or a tuple (function, args, error_msg),
                        in which, args and error_msg are optional. args is
                        either a value or a tuple if multiple arguments.
                        This can also be a list containing multiple function
                        or tuple. In this case, these actions are called in
                        sequence.
          check_status: Check the return value of action function. If not
                        succeed, raises a TestFail exception.

        Returns:
          The result value of the action function.

        Raises:
          error.TestError: An error when the action function is not callable.
          error.TestFail: When check_status=True, action function not succeed.
        """
        if isinstance(action_tuple, list):
            return all([self._call_action(action, check_status=check_status)
                        for action in action_tuple])

        action = action_tuple
        args = ()
        error_msg = 'Not succeed'
        if isinstance(action_tuple, tuple):
            action = action_tuple[0]
            if len(action_tuple) >= 2:
                args = action_tuple[1]
                if not isinstance(args, tuple):
                    args = (args,)
            if len(action_tuple) >= 3:
                error_msg = action_tuple[2]

        if action is None:
            return

        if not callable(action):
            raise error.TestError('action is not callable!')

        info_msg = 'calling %s' % str(action)
        if args:
            info_msg += ' with args %s' % str(args)
        logging.info(info_msg)
        ret = action(*args)

        if check_status and not ret:
            raise error.TestFail('%s: %s returning %s' %
                                 (error_msg, info_msg, str(ret)))
        return ret


    def run_shutdown_process(self, shutdown_action, pre_power_action=None,
            post_power_action=None, shutdown_timeout=None):
        """Run shutdown_action(), which makes DUT shutdown, and power it on.

        Args:
          shutdown_action: a function which makes DUT shutdown, like pressing
                           power key.
          pre_power_action: a function which is called before next power on.
          post_power_action: a function which is called after next power on.
          shutdown_timeout: a timeout to confirm DUT shutdown.

        Raises:
          error.TestFail: if the shutdown_action() failed to turn DUT off.
        """
        self._call_action(shutdown_action)
        logging.info('Wait to ensure DUT shut down...')
        try:
            if shutdown_timeout is None:
                shutdown_timeout = self.delay.shutdown_timeout
            self.wait_for_client(timeout=shutdown_timeout)
            raise error.TestFail(
                    'Should shut the device down after calling %s.' %
                    str(shutdown_action))
        except AssertionError:
            logging.info(
                'DUT is surely shutdown. We are going to power it on again...')

        if pre_power_action:
            self._call_action(pre_power_action)
        self.servo.power_short_press()
        if post_power_action:
            self._call_action(post_power_action)


    def register_faft_template(self, template):
        """Register FAFT template, the default FAFT_STEP of each step.

        Any missing field falls back to the original faft_template.

        Args:
          template: A FAFT_STEP dict.
        """
        self._faft_template.update(template)


    def register_faft_sequence(self, sequence):
        """Register FAFT sequence.

        Args:
          sequence: A FAFT_SEQUENCE array which consisted of FAFT_STEP dicts.
        """
        self._faft_sequence = sequence


    def run_faft_step(self, step, no_reboot=False, next_step=None):
        """Run a single FAFT step.

        Any missing field falls back to faft_template. An empty step means
        running the default faft_template.

        Args:
          step: A FAFT_STEP dict.
          no_reboot: True to prevent running reboot_action and firmware_action.
          next_step: Optional, a FAFT_STEP dict of the next step, which is used
                     for diagnostic.

        Raises:
          error.TestError: An error when the given step is not valid.
          error.TestFail: Test failed in waiting DUT reboot.
        """
        FAFT_STEP_KEYS = ('state_checker', 'userspace_action', 'reboot_action',
                          'firmware_action', 'install_deps_after_boot')

        test = {}
        test.update(self._faft_template)
        test.update(step)

        for key in test:
            if key not in FAFT_STEP_KEYS:
                raise error.TestError('Invalid key in FAFT step: %s', key)

        if test['state_checker']:
            self._call_action(test['state_checker'], check_status=True)

        boot_id = None
        try:
          boot_id = self._client.get_boot_id()
        except error.AutoservRunError:
          logging.warning('Failed to get boot id.')

        self._call_action(test['userspace_action'])

        # Don't run reboot_action and firmware_action if no_reboot is True.
        if not no_reboot:
            self._call_action(test['reboot_action'])
            self.wait_for_client_offline(orig_boot_id=boot_id)
            self._call_action(test['firmware_action'])

            try:
                if 'install_deps_after_boot' in test:
                    self.wait_for_client(
                            install_deps=test['install_deps_after_boot'])
                else:
                    self.wait_for_client()
            except AssertionError:
                logging.error('wait_for_client() timed out.')
                self._restore_routine_from_timeout(next_step)


    def run_faft_sequence(self):
        """Run FAFT sequence which was previously registered."""
        sequence = self._faft_sequence
        for index, step in enumerate(sequence):
            logging.info('======== Running FAFT sequence step %d ========',
                         index + 1)
            # Don't reboot in the last step.
            if index == len(sequence) - 1:
                self.run_faft_step(step, no_reboot=True)
            else:
                self.run_faft_step(step, next_step=sequence[index + 1])


    def get_current_firmware_sha(self):
        """Get current firmware sha of body and vblock.

        Returns:
            Current firmware sha follows the order (
                vblock_a_sha, body_a_sha, vblock_b_sha, body_b_sha)
        """
        current_firmware_sha = (self.faft_client.bios.get_sig_sha('a'),
                                self.faft_client.bios.get_body_sha('a'),
                                self.faft_client.bios.get_sig_sha('b'),
                                self.faft_client.bios.get_body_sha('b'))
        return current_firmware_sha


    def is_firmware_changed(self):
        """Check if the current firmware changed, by comparing its SHA.

        Returns:
            True if it is changed, otherwise Flase.
        """
        # Device may not be rebooted after test.
        self.faft_client.bios.reload()

        current_sha = self.get_current_firmware_sha()

        if current_sha == self._backup_firmware_sha:
            return False
        else:
            corrupt_VBOOTA = (current_sha[0] != self._backup_firmware_sha[0])
            corrupt_FVMAIN = (current_sha[1] != self._backup_firmware_sha[1])
            corrupt_VBOOTB = (current_sha[2] != self._backup_firmware_sha[2])
            corrupt_FVMAINB = (current_sha[3] != self._backup_firmware_sha[3])
            logging.info("Firmware changed:")
            logging.info('VBOOTA is changed: %s', corrupt_VBOOTA)
            logging.info('VBOOTB is changed: %s', corrupt_VBOOTB)
            logging.info('FVMAIN is changed: %s', corrupt_FVMAIN)
            logging.info('FVMAINB is changed: %s', corrupt_FVMAINB)
            return True


    def backup_firmware(self, suffix='.original'):
        """Backup firmware to file, and then send it to host.

        Args:
            suffix: a string appended to backup file name
        """
        remote_temp_dir = self.faft_client.system.create_temp_dir()
        self.faft_client.bios.dump_whole(os.path.join(remote_temp_dir, 'bios'))
        self._client.get_file(os.path.join(remote_temp_dir, 'bios'),
                              os.path.join(self.resultsdir, 'bios' + suffix))

        self._backup_firmware_sha = self.get_current_firmware_sha()
        logging.info('Backup firmware stored in %s with suffix %s',
            self.resultsdir, suffix)


    def is_firmware_saved(self):
        """Check if a firmware saved (called backup_firmware before).

        Returns:
            True if the firmware is backuped; otherwise False.
        """
        return self._backup_firmware_sha != ()


    def clear_saved_firmware(self):
        """Clear the firmware saved by the method backup_firmware."""
        self._backup_firmware_sha = ()


    def restore_firmware(self, suffix='.original'):
        """Restore firmware from host in resultsdir.

        Args:
            suffix: a string appended to backup file name
        """
        if not self.is_firmware_changed():
            return

        # Backup current corrupted firmware.
        self.backup_firmware(suffix='.corrupt')

        # Restore firmware.
        remote_temp_dir = self.faft_client.system.create_temp_dir()
        self._client.send_file(os.path.join(self.resultsdir, 'bios' + suffix),
                               os.path.join(remote_temp_dir, 'bios'))

        self.faft_client.bios.write_whole(
            os.path.join(remote_temp_dir, 'bios'))
        self.sync_and_warm_reboot()
        self.wait_for_client_offline()
        self.wait_dev_screen_and_ctrl_d()
        self.wait_for_client()

        logging.info('Successfully restore firmware.')


    def setup_firmwareupdate_shellball(self, shellball=None):
        """Deside a shellball to use in firmware update test.

        Check if there is a given shellball, and it is a shell script. Then,
        send it to the remote host. Otherwise, use
        /usr/sbin/chromeos-firmwareupdate.

        Args:
            shellball: path of a shellball or default to None.

        Returns:
            Path of shellball in remote host.
            If use default shellball, reutrn None.
        """
        updater_path = None
        if shellball:
            # Determine the firmware file is a shellball or a raw binary.
            is_shellball = (utils.system_output("file %s" % shellball).find(
                    "shell script") != -1)
            if is_shellball:
                logging.info('Device will update firmware with shellball %s',
                             shellball)
                temp_dir = self.faft_client.system.create_temp_dir(
                            'shellball_')
                temp_shellball = os.path.join(temp_dir, 'updater.sh')
                self._client.send_file(shellball, temp_shellball)
                updater_path = temp_shellball
            else:
                raise error.TestFail(
                    'The given shellball is not a shell script.')
            return updater_path
