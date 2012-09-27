# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ctypes
import fdpexpect
import logging
import os
import pexpect
import re
import sys
import tempfile
import time
import xmlrpclib

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.faft_client_attribute import FAFTClientAttribute
from autotest_lib.server.cros.servo_test import ServoTest
from autotest_lib.site_utils import lab_test

dirname = os.path.dirname(sys.modules[__name__].__file__)
autotest_dir = os.path.abspath(os.path.join(dirname, "..", ".."))
cros_dir = os.path.join(autotest_dir, "..", "..", "..", "..")

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
        _customized_ctrl_d_key_command: The customized Ctrl-D key command
            instead of sending key via servo board.
        _customized_enter_key_command: The customized Enter key command instead
            of sending key via servo board.
        _customized_space_key_command: The customized Space key command instead
            of sending key via servo board.
        _customized_rec_reboot_command: The customized recovery reboot command
            instead of sending key combination of Power + Esc + F3 for
            triggering recovery reboot.
        _install_image_path: The path of Chrome OS test image to be installed.
        _firmware_update: Boolean. True if firmware update needed after
            installing the image.
    """
    version = 1


    # Mapping of partition number of kernel and rootfs.
    KERNEL_MAP = {'a':'2', 'b':'4', '2':'2', '4':'4', '3':'2', '5':'4'}
    ROOTFS_MAP = {'a':'3', 'b':'5', '2':'3', '4':'5', '3':'3', '5':'5'}
    OTHER_KERNEL_MAP = {'a':'4', 'b':'2', '2':'4', '4':'2', '3':'4', '5':'2'}
    OTHER_ROOTFS_MAP = {'a':'5', 'b':'3', '2':'5', '4':'3', '3':'5', '5':'3'}

    # Delay between power-on and firmware screen.
    FIRMWARE_SCREEN_DELAY = 10
    # Delay between passing firmware screen and text mode warning screen.
    TEXT_SCREEN_DELAY = 20
    # Delay of loading the USB kernel.
    USB_LOAD_DELAY = 10
    # Delay between USB plug-out and plug-in.
    USB_PLUG_DELAY = 10
    # Delay after running the 'sync' command.
    SYNC_DELAY = 5
    # Delay for waiting client to return before EC reboot
    EC_REBOOT_DELAY = 1
    # Delay for waiting client to full power off
    FULL_POWER_OFF_DELAY = 30
    # Delay between EC reboot and pressing power button
    POWER_BTN_DELAY = 0.5
    # Delay of EC software sync hash calculating time
    SOFTWARE_SYNC_DELAY = 6
    # Delay between EC boot and ChromeEC console functional
    EC_BOOT_DELAY = 0.5
    # Duration of holding cold_reset to reset device
    COLD_RESET_DELAY = 0.1

    # The developer screen timeouts fit our spec.
    DEV_SCREEN_TIMEOUT = 30

    CHROMEOS_MAGIC = "CHROMEOS"
    CORRUPTED_MAGIC = "CORRUPTD"

    # Recovery reason codes, copied from:
    #     vboot_reference/firmware/lib/vboot_nvstorage.h
    #     vboot_reference/firmware/lib/vboot_struct.h
    RECOVERY_REASON = {
        # Recovery not requested
        'NOT_REQUESTED':      '0',   # 0x00
        # Recovery requested from legacy utility
        'LEGACY':             '1',   # 0x01
        # User manually requested recovery via recovery button
        'RO_MANUAL':          '2',   # 0x02
        # RW firmware failed signature check
        'RO_INVALID_RW':      '3',   # 0x03
        # S3 resume failed
        'RO_S3_RESUME':       '4',   # 0x04
        # TPM error in read-only firmware
        'RO_TPM_ERROR':       '5',   # 0x05
        # Shared data error in read-only firmware
        'RO_SHARED_DATA':     '6',   # 0x06
        # Test error from S3Resume()
        'RO_TEST_S3':         '7',   # 0x07
        # Test error from LoadFirmwareSetup()
        'RO_TEST_LFS':        '8',   # 0x08
        # Test error from LoadFirmware()
        'RO_TEST_LF':         '9',   # 0x09
        # RW firmware failed signature check
        'RW_NOT_DONE':        '16',  # 0x10
        'RW_DEV_MISMATCH':    '17',  # 0x11
        'RW_REC_MISMATCH':    '18',  # 0x12
        'RW_VERIFY_KEYBLOCK': '19',  # 0x13
        'RW_KEY_ROLLBACK':    '20',  # 0x14
        'RW_DATA_KEY_PARSE':  '21',  # 0x15
        'RW_VERIFY_PREAMBLE': '22',  # 0x16
        'RW_FW_ROLLBACK':     '23',  # 0x17
        'RW_HEADER_VALID':    '24',  # 0x18
        'RW_GET_FW_BODY':     '25',  # 0x19
        'RW_HASH_WRONG_SIZE': '26',  # 0x1A
        'RW_VERIFY_BODY':     '27',  # 0x1B
        'RW_VALID':           '28',  # 0x1C
        # Read-only normal path requested by firmware preamble, but
        # unsupported by firmware.
        'RW_NO_RO_NORMAL':    '29',  # 0x1D
        # Firmware boot failure outside of verified boot
        'RO_FIRMWARE':        '32',  # 0x20
        # Recovery mode TPM initialization requires a system reboot.
        # The system was already in recovery mode for some other reason
        # when this happened.
        'RO_TPM_REBOOT':      '33',  # 0x21
        # Unspecified/unknown error in read-only firmware
        'RO_UNSPECIFIED':     '63',  # 0x3F
        # User manually requested recovery by pressing a key at developer
        # warning screen.
        'RW_DEV_SCREEN':      '65',  # 0x41
        # No OS kernel detected
        'RW_NO_OS':           '66',  # 0x42
        # OS kernel failed signature check
        'RW_INVALID_OS':      '67',  # 0x43
        # TPM error in rewritable firmware
        'RW_TPM_ERROR':       '68',  # 0x44
        # RW firmware in dev mode, but dev switch is off.
        'RW_DEV_MISMATCH':    '69',  # 0x45
        # Shared data error in rewritable firmware
        'RW_SHARED_DATA':     '70',  # 0x46
        # Test error from LoadKernel()
        'RW_TEST_LK':         '71',  # 0x47
        # No bootable disk found
        'RW_NO_DISK':         '72',  # 0x48
        # Unspecified/unknown error in rewritable firmware
        'RW_UNSPECIFIED':     '127', # 0x7F
        # DM-verity error
        'KE_DM_VERITY':       '129', # 0x81
        # Unspecified/unknown error in kernel
        'KE_UNSPECIFIED':     '191', # 0xBF
        # Recovery mode test from user-mode
        'US_TEST':            '193', # 0xC1
        # Unspecified/unknown error in user-mode
        'US_UNSPECIFIED':     '255', # 0xFF
    }

    # GBB flags
    GBB_FLAG_DEV_SCREEN_SHORT_DELAY    = 0x00000001
    GBB_FLAG_LOAD_OPTION_ROMS          = 0x00000002
    GBB_FLAG_ENABLE_ALTERNATE_OS       = 0x00000004
    GBB_FLAG_FORCE_DEV_SWITCH_ON       = 0x00000008
    GBB_FLAG_FORCE_DEV_BOOT_USB        = 0x00000010
    GBB_FLAG_DISABLE_FW_ROLLBACK_CHECK = 0x00000020
    GBB_FLAG_ENTER_TRIGGERS_TONORM     = 0x00000040

    # VbSharedData flags
    # Copied from vboot_reference/firmware/include/vboot_struct.h
    VDAT_FLAG_FWB_TRIED                = 0x00000001
    VDAT_FLAG_KERNEL_KEY_VERIFIED      = 0x00000002
    VDAT_FLAG_LF_DEV_SWITCH_ON         = 0x00000004
    VDAT_FLAG_LF_USE_RO_NORMAL         = 0x00000008
    VDAT_FLAG_BOOT_DEV_SWITCH_ON       = 0x00000010
    VDAT_FLAG_BOOT_REC_SWITCH_ON       = 0x00000020
    VDAT_FLAG_BOOT_FIRMWARE_WP_ENABLED = 0x00000040
    VDAT_FLAG_BOOT_S3_RESUME           = 0x00000100
    VDAT_FLAG_BOOT_RO_NORMAL_SUPPORT   = 0x00000200
    VDAT_FLAG_HONOR_VIRT_DEV_SWITCH    = 0x00000400
    VDAT_FLAG_EC_SOFTWARE_SYNC         = 0x00000800
    VDAT_FLAG_EC_SLOW_UPDATE           = 0x00001000

    # Firmware preamble flags
    PREAMBLE_USE_RO_NORMAL             = 0x00000001

    _faft_template = {}
    _faft_sequence = ()

    _customized_ctrl_d_key_command = None
    _customized_enter_key_command = None
    _customized_space_key_command = None
    _customized_rec_reboot_command = None
    _install_image_path = None
    _firmware_update = False

    _backup_firmware_name = ('VBOOTA', 'VBOOTB', 'FVMAIN', 'FVMAINB')
    _backup_firmware_sha = ()


    def initialize(self, host, cmdline_args, use_pyauto=False, use_faft=False):
        # Parse arguments from command line
        args = {}
        for arg in cmdline_args:
            match = re.search("^(\w+)=(.+)", arg)
            if match:
                args[match.group(1)] = match.group(2)

        # Keep the arguments which will be used later.
        if 'ctrl_d_cmd' in args:
            self._customized_ctrl_d_key_command = args['ctrl_d_cmd']
            logging.info('Customized Ctrl-D key command: %s' %
                    self._customized_ctrl_d_key_command)
        if 'enter_cmd' in args:
            self._customized_enter_key_command = args['enter_cmd']
            logging.info('Customized Enter key command: %s' %
                    self._customized_enter_key_command)
        if 'space_cmd' in args:
            self._customized_space_key_command = args['space_cmd']
            logging.info('Customized Space key command: %s' %
                    self._customized_space_key_command)
        if 'rec_reboot_cmd' in args:
            self._customized_rec_reboot_command = args['rec_reboot_cmd']
            logging.info('Customized recovery reboot command: %s' %
                    self._customized_rec_reboot_command)
        if 'image' in args:
            self._install_image_path = args['image']
            logging.info('Install Chrome OS test image path: %s' %
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
                    self.faft_client.get_platform_name())

            # Setting up key matrix mapping
            self.servo.set_key_matrix(self.client_attr.key_matrix_layout)


    def setup(self):
        """Autotest setup function."""
        super(FAFTSequence, self).setup()
        if not self._remote_infos['faft']['used']:
            raise error.TestError('The use_faft flag should be enabled.')
        self.register_faft_template({
            'state_checker': (None),
            'userspace_action': (None),
            'reboot_action': (self.sync_and_warm_reboot),
            'firmware_action': (None)
        })
        self.clear_set_gbb_flags(self.GBB_FLAG_FORCE_DEV_SWITCH_ON |
                                 self.GBB_FLAG_DEV_SCREEN_SHORT_DELAY,
                                 self.GBB_FLAG_ENTER_TRIGGERS_TONORM)
        if self._install_image_path:
            self.install_test_image(self._install_image_path,
                                    self._firmware_update)


    def cleanup(self):
        """Autotest cleanup function."""
        self._faft_sequence = ()
        self._faft_template = {}
        super(FAFTSequence, self).cleanup()


    def reset_client(self):
        """Reset client, if necessary.

        This method is called when the client is not responsive. It may be
        caused by the following cases:
          - network flaky (can be recovered by replugging the Ethernet);
          - halt on a firmware screen without timeout, e.g. REC_INSERT screen;
          - corrupted firmware;
          - corrutped OS image.
        """
        # DUT works fine, done.
        if self._ping_test(self._client.ip, timeout=5):
            return

        # TODO(waihong@chromium.org): Implement replugging the Ethernet in the
        # first reset item.

        # DUT may halt on a firmware screen. Try cold reboot.
        logging.info('Try cold reboot...')
        self.cold_reboot()
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
            self.ensure_client_in_recovery()
            logging.info('Try restore the original firmware...')
            if self.is_firmware_changed():
                try:
                    self.restore_firmware()
                    return
                except AssertionError:
                    logging.info('Restoring firmware doesn\'t help.')

        # DUT may be broken by a corrupted OS image. Restore OS image.
        self.ensure_client_in_recovery()
        logging.info('Try restore the OS image...')
        self.faft_client.run_shell_command('chromeos-install --yes')
        self.sync_and_warm_reboot()
        self.wait_for_client_offline()
        try:
            self.wait_for_client(install_deps=True)
            logging.info('Successfully restore OS image.')
            return
        except AssertionError:
            logging.info('Restoring OS image doesn\'t help.')


    def ensure_client_in_recovery(self):
        """Ensure client in recovery boot; reboot into it if necessary.

        Raises:
            error.TestError: if failed to boot the USB image.
        """
        # DUT works fine and is already in recovery boot, done.
        if self._ping_test(self._client.ip, timeout=5):
            if self.crossystem_checker({'mainfw_type': 'recovery'}):
                return

        logging.info('Try boot into USB image...')
        self.servo.enable_usb_hub(host=True)
        self.enable_rec_mode_and_reboot()
        self.wait_fw_screen_and_plug_usb()
        try:
            self.wait_for_client(install_deps=True)
        except AssertionError:
            raise error.TestError('Failed to boot the USB image.')


    def assert_test_image_in_usb_disk(self, usb_dev=None):
        """Assert an USB disk plugged-in on servo and a test image inside.

        Args:
          usb_dev: A string of USB stick path on the host, like '/dev/sdc'.
                   If None, it is detected automatically.

        Raises:
          error.TestError: if USB disk not detected or not a test image.
        """
        if usb_dev:
            assert self.servo.get('usb_mux_sel1') == 'servo_sees_usbkey'
        else:
            self.servo.enable_usb_hub(host=True)
            usb_dev = self.servo.probe_host_usb_dev()
            if not usb_dev:
                raise error.TestError(
                        'An USB disk should be plugged in the servo board.')

        tmp_dir = tempfile.mkdtemp()
        utils.system('sudo mount -r -t ext2 %s3 %s' % (usb_dev, tmp_dir))
        code = utils.system(
               'grep -qE "(Test Build|testimage-channel)" %s/etc/lsb-release' %
               tmp_dir, ignore_status=True)
        utils.system('sudo umount %s' % tmp_dir)
        os.removedirs(tmp_dir)
        if code != 0:
            raise error.TestError(
                    'The image in the USB disk should be a test image.')


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
            image_path: Path on the host to the test image.
            firmware_update: Also update the firmware after installing.
        """
        build_ver, build_hash = lab_test.VerifyImageAndGetId(cros_dir,
                                                             image_path)
        logging.info('Processing build: %s %s' % (build_ver, build_hash))

        # Reuse the servo method that uses the servo USB key to install
        # the test image.
        self.servo.image_to_servo_usb(image_path)

        # DUT is powered off while imaging servo USB.
        # Now turn it on.
        self.servo.power_short_press()
        self.wait_for_client()
        self.servo.set('usb_mux_sel1', 'dut_sees_usbkey')

        install_cmd = 'chromeos-install --yes'
        if firmware_update:
            install_cmd += ' && chromeos-firmwareupdate --mode recovery'

        self.register_faft_sequence((
            {   # Step 1, request recovery boot
                'state_checker': (self.crossystem_checker, {
                    'mainfw_type': ('developer', 'normal'),
                }),
                'userspace_action': self.faft_client.request_recovery_boot,
                'firmware_action': self.wait_fw_screen_and_plug_usb,
                'install_deps_after_boot': True,
            },
            {   # Step 2, expected recovery boot
                'state_checker': (self.crossystem_checker, {
                    'mainfw_type': 'recovery',
                    'recovery_reason' : self.RECOVERY_REASON['US_TEST'],
                }),
                'userspace_action': (self.faft_client.run_shell_command,
                                     install_cmd),
                'reboot_action': self.cold_reboot,
                'install_deps_after_boot': True,
            },
            {   # Step 3, expected normal or developer boot (not recovery)
                'state_checker': (self.crossystem_checker, {
                    'mainfw_type': ('developer', 'normal')
                }),
            },
        ))
        self.run_faft_sequence()
        # 'Unplug' any USB keys in the servo from the dut.
        self.servo.disable_usb_hub()


    def clear_set_gbb_flags(self, clear_mask, set_mask):
        """Clear and set the GBB flags in the current flashrom.

        Args:
          clear_mask: A mask of flags to be cleared.
          set_mask: A mask of flags to be set.
        """
        gbb_flags = self.faft_client.get_gbb_flags()
        new_flags = gbb_flags & ctypes.c_uint32(~clear_mask).value | set_mask

        if (gbb_flags != new_flags):
            logging.info('Change the GBB flags from 0x%x to 0x%x.' %
                         (gbb_flags, new_flags))
            self.faft_client.run_shell_command(
                    '/usr/share/vboot/bin/set_gbb_flags.sh 0x%x' % new_flags)
            self.faft_client.reload_firmware()
            # If changing FORCE_DEV_SWITCH_ON flag, reboot to get a clear state
            if ((gbb_flags ^ new_flags) & self.GBB_FLAG_FORCE_DEV_SWITCH_ON):
                self.run_faft_step({
                    'firmware_action': self.wait_fw_screen_and_ctrl_d,
                })


    def _open_uart_pty(self):
        """Open UART pty and spawn pexpect object.

        Returns:
          Tuple (fd, child): fd is the file descriptor of opened UART pty, and
            child is a fdpexpect object tied to it.
        """
        fd = os.open(self.servo.get("uart1_pty"), os.O_RDWR | os.O_NONBLOCK)
        child = fdpexpect.fdspawn(fd)
        return (fd, child)


    def _flush_uart_pty(self, child):
        """Flush UART output to prevent previous pending message interferring.

        Args:
          child: The fdpexpect object tied to UART pty.
        """
        child.sendline("")
        while True:
            try:
                child.expect(".", timeout=0.01)
            except pexpect.TIMEOUT:
                break


    def _uart_send(self, child, line):
        """Flush and send command through UART.

        Args:
          child: The pexpect object tied to UART pty.
          line: String to send through UART.

        Raises:
          error.TestFail: Raised when writing to UART fails.
        """
        logging.info("Sending UART command: %s" % line)
        self._flush_uart_pty(child)
        if child.sendline(line) != len(line) + 1:
            raise error.TestFail("Failed to send UART command.")


    def send_uart_command(self, command):
        """Send command through UART.

        This function open UART pty when called, and then command is sent
        through UART.

        Args:
          command: The command string to send.

        Raises:
          error.TestFail: Raised when writing to UART fails.
        """
        (fd, child) = self._open_uart_pty()
        try:
            self._uart_send(child, command)
        finally:
            os.close(fd)


    def send_uart_command_get_output(self, command, regex_list, timeout=1):
        """Send command through UART and wait for response.

        This function waits for response message matching regular expressions.

        Args:
          command: The command sent.
          regex_list: List of regular expressions used to match response message.
            Note, list must be ordered.

        Returns:
          List of match objects of response message.

        Raises:
          error.TestFail: If timed out waiting for EC response.
        """
        if not isinstance(regex_list, list):
            regex_list = [regex_list]
        result_list = []
        (fd, child) = self._open_uart_pty()
        try:
            self._uart_send(child, command)
            for regex in regex_list:
                child.expect(regex, timeout=timeout)
                result_list.append(child.match)
        except pexpect.TIMEOUT:
            raise error.TestFail("Timeout waiting for UART response.")
        finally:
            os.close(fd)
        return result_list


    def check_ec_capability(self, required_cap=[], suppress_warning=False):
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

        for cap in required_cap:
            if cap not in self.client_attr.ec_capability:
                if not suppress_warning:
                    logging.warn('Requires EC capability "%s" to run this '
                                 'test.' % cap)
                return False

        return True


    def _parse_crossystem_output(self, lines):
        """Parse the crossystem output into a dict.

        Args:
          lines: The list of crossystem output strings.

        Returns:
          A dict which contains the crossystem keys/values.

        Raises:
          error.TestError: If wrong format in crossystem output.

        >>> seq = FAFTSequence()
        >>> seq._parse_crossystem_output([ \
                "arch          = x86    # Platform architecture", \
                "cros_debug    = 1      # OS should allow debug", \
            ])
        {'cros_debug': '1', 'arch': 'x86'}
        >>> seq._parse_crossystem_output([ \
                "arch=x86", \
            ])
        Traceback (most recent call last):
            ...
        TestError: Failed to parse crossystem output: arch=x86
        >>> seq._parse_crossystem_output([ \
                "arch          = x86    # Platform architecture", \
                "arch          = arm    # Platform architecture", \
            ])
        Traceback (most recent call last):
            ...
        TestError: Duplicated crossystem key: arch
        """
        pattern = "^([^ =]*) *= *(.*[^ ]) *# [^#]*$"
        parsed_list = {}
        for line in lines:
            matched = re.match(pattern, line.strip())
            if not matched:
                raise error.TestError("Failed to parse crossystem output: %s"
                                      % line)
            (name, value) = (matched.group(1), matched.group(2))
            if name in parsed_list:
                raise error.TestError("Duplicated crossystem key: %s" % name)
            parsed_list[name] = value
        return parsed_list


    def crossystem_checker(self, expected_dict):
        """Check the crossystem values matched.

        Given an expect_dict which describes the expected crossystem values,
        this function check the current crossystem values are matched or not.

        Args:
          expected_dict: A dict which contains the expected values.

        Returns:
          True if the crossystem value matched; otherwise, False.
        """
        lines = self.faft_client.run_shell_command_get_output('crossystem')
        got_dict = self._parse_crossystem_output(lines)
        for key in expected_dict:
            if key not in got_dict:
                logging.info('Expected key "%s" not in crossystem result' % key)
                return False
            if isinstance(expected_dict[key], str):
                if got_dict[key] != expected_dict[key]:
                    logging.info("Expected '%s' value '%s' but got '%s'" %
                                 (key, expected_dict[key], got_dict[key]))
                    return False
            elif isinstance(expected_dict[key], tuple):
                # Expected value is a tuple of possible actual values.
                if got_dict[key] not in expected_dict[key]:
                    logging.info("Expected '%s' values %s but got '%s'" %
                                 (key, str(expected_dict[key]), got_dict[key]))
                    return False
            else:
                logging.info("The expected_dict is neither a str nor a dict.")
                return False
        return True


    def vdat_flags_checker(self, mask, value):
        """Check the flags from VbSharedData matched.

        This function checks the masked flags from VbSharedData using crossystem
        are matched the given value.

        Args:
          mask: A bitmask of flags to be matched.
          value: An expected value.

        Returns:
          True if the flags matched; otherwise, False.
        """
        lines = self.faft_client.run_shell_command_get_output(
                    'crossystem vdat_flags')
        vdat_flags = int(lines[0], 16)
        if vdat_flags & mask != value:
            logging.info("Expected vdat_flags 0x%x mask 0x%x but got 0x%x" %
                         (value, mask, vdat_flags))
            return False
        return True


    def ro_normal_checker(self, expected_fw=None, twostop=False):
        """Check the current boot uses RO boot.

        Args:
          expected_fw: A string of expected firmware, 'A', 'B', or
                       None if don't care.
          twostop: True to expect a TwoStop boot; False to expect a RO boot.

        Returns:
          True if the currect boot firmware matched and used RO boot;
          otherwise, False.
        """
        crossystem_dict = {'tried_fwb': '0'}
        if expected_fw:
            crossystem_dict['mainfw_act'] = expected_fw.upper()
        if self.check_ec_capability(suppress_warning=True):
            crossystem_dict['ecfw_act'] = ('RW' if twostop else 'RO')

        return (self.vdat_flags_checker(
                    self.VDAT_FLAG_LF_USE_RO_NORMAL,
                    0 if twostop else self.VDAT_FLAG_LF_USE_RO_NORMAL) and
                self.crossystem_checker(crossystem_dict))


    def root_part_checker(self, expected_part):
        """Check the partition number of the root device matched.

        Args:
          expected_part: A string containing the number of the expected root
                         partition.

        Returns:
          True if the currect root  partition number matched; otherwise, False.
        """
        part = self.faft_client.get_root_part()[-1]
        if self.ROOTFS_MAP[expected_part] != part:
            logging.info("Expected root part %s but got %s" %
                         (self.ROOTFS_MAP[expected_part], part))
            return False
        return True


    def ec_act_copy_checker(self, expected_copy):
        """Check the EC running firmware copy matches.

        Args:
          expected_copy: A string containing 'RO', 'A', or 'B' indicating
                         the expected copy of EC running firmware.

        Returns:
          True if the current EC running copy matches; otherwise, False.
        """
        lines = self.faft_client.run_shell_command_get_output('ectool version')
        pattern = re.compile("Firmware copy: (.*)")
        for line in lines:
            matched = pattern.match(line)
            if matched and matched.group(1) == expected_copy:
                return True
        return False


    def check_root_part_on_non_recovery(self, part):
        """Check the partition number of root device and on normal/dev boot.

        Returns:
            True if the root device matched and on normal/dev boot;
            otherwise, False.
        """
        return self.root_part_checker(part) and \
                self.crossystem_checker({
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
        root_dev = self.faft_client.get_root_dev()
        logging.info('Copying kernel from %s to %s. Please wait...' %
                     (from_part, to_part))
        self.faft_client.run_shell_command('dd if=%s of=%s bs=4M' %
                (self._join_part(root_dev, self.KERNEL_MAP[from_part]),
                 self._join_part(root_dev, self.KERNEL_MAP[to_part])))
        logging.info('Copying rootfs from %s to %s. Please wait...' %
                     (from_part, to_part))
        self.faft_client.run_shell_command('dd if=%s of=%s bs=4M' %
                (self._join_part(root_dev, self.ROOTFS_MAP[from_part]),
                 self._join_part(root_dev, self.ROOTFS_MAP[to_part])))


    def ensure_kernel_boot(self, part):
        """Ensure the request kernel boot.

        If not, it duplicates the current kernel to the requested kernel
        and sets the requested higher priority to ensure it boot.

        Args:
          part: A string of kernel partition number or 'a'/'b'.
        """
        if not self.root_part_checker(part):
            if self.faft_client.diff_kernel_a_b():
                self.copy_kernel_and_rootfs(
                        from_part=self.OTHER_KERNEL_MAP[part],
                        to_part=part)
            self.run_faft_step({
                'userspace_action': (self.reset_and_prioritize_kernel, part),
            })


    def set_hardware_write_protect(self, enabled):
        """Set hardware write protect pin.

        Args:
          enable: True if asserting write protect pin. Otherwise, False.
        """
        self.servo.set('fw_wp_vref', self.client_attr.wp_voltage)
        self.servo.set('fw_wp_en', 'on')
        self.servo.set('fw_wp', 'on' if enabled else 'off')


    def set_EC_write_protect_and_reboot(self, enabled):
        """Set EC write protect status and reboot to take effect.

        EC write protect is only activated if both hardware write protect pin
        is asserted and software write protect flag is set. Also, a reboot is
        required for write protect to take effect.

        Since the software write protect flag cannot be unset if hardware write
        protect pin is asserted, we need to deasserted the pin first if we are
        deactivating write protect. Similarly, a reboot is required before we
        can modify the software flag.

        This method asserts/deasserts hardware write protect pin first, and
        set corresponding EC software write protect flag.

        Args:
          enable: True if activating EC write protect. Otherwise, False.
        """
        self.set_hardware_write_protect(enabled)
        if enabled:
            # Set write protect flag and reboot to take effect.
            self.send_uart_command("flashwp enable")
            self.sync_and_ec_reboot()
        else:
            # Reboot after deasserting hardware write protect pin to deactivate
            # write protect. And then remove software write protect flag.
            self.sync_and_ec_reboot()
            self.send_uart_command("flashwp disable")


    def send_ctrl_d_to_dut(self):
        """Send Ctrl-D key to DUT."""
        if self._customized_ctrl_d_key_command:
            logging.info('running the customized Ctrl-D key command')
            os.system(self._customized_ctrl_d_key_command)
        else:
            self.servo.ctrl_d()


    def send_enter_to_dut(self):
        """Send Enter key to DUT."""
        if self._customized_enter_key_command:
            logging.info('running the customized Enter key command')
            os.system(self._customized_enter_key_command)
        else:
            self.servo.enter_key()


    def send_space_to_dut(self):
        """Send Space key to DUT."""
        if self._customized_space_key_command:
            logging.info('running the customized Space key command')
            os.system(self._customized_space_key_command)
        else:
            # Send the alternative key combinaton of space key to servo.
            self.servo.ctrl_refresh_key()


    def wait_fw_screen_and_ctrl_d(self):
        """Wait for firmware warning screen and press Ctrl-D."""
        time.sleep(self.FIRMWARE_SCREEN_DELAY)
        self.send_ctrl_d_to_dut()


    def wait_fw_screen_and_trigger_recovery(self, need_dev_transition=False):
        """Wait for firmware warning screen and trigger recovery boot."""
        time.sleep(self.FIRMWARE_SCREEN_DELAY)
        self.send_enter_to_dut()

        # For Alex/ZGB, there is a dev warning screen in text mode.
        # Skip it by pressing Ctrl-D.
        if need_dev_transition:
            time.sleep(self.TEXT_SCREEN_DELAY)
            self.send_ctrl_d_to_dut()


    def wait_fw_screen_and_unplug_usb(self):
        """Wait for firmware warning screen and then unplug the servo USB."""
        time.sleep(self.USB_LOAD_DELAY)
        self.servo.set('usb_mux_sel1', 'servo_sees_usbkey')
        time.sleep(self.USB_PLUG_DELAY)


    def wait_fw_screen_and_plug_usb(self):
        """Wait for firmware warning screen and then unplug and plug the USB."""
        self.wait_fw_screen_and_unplug_usb()
        self.servo.set('usb_mux_sel1', 'dut_sees_usbkey')


    def wait_fw_screen_and_press_power(self):
        """Wait for firmware warning screen and press power button."""
        time.sleep(self.FIRMWARE_SCREEN_DELAY)
        # While the firmware screen, the power button probing loop sleeps
        # 0.25 second on every scan. Use the normal delay (1.2 second) for
        # power press.
        self.servo.power_normal_press()


    def wait_longer_fw_screen_and_press_power(self):
        """Wait for firmware screen without timeout and press power button."""
        time.sleep(self.DEV_SCREEN_TIMEOUT)
        self.wait_fw_screen_and_press_power()


    def wait_fw_screen_and_close_lid(self):
        """Wait for firmware warning screen and close lid."""
        time.sleep(self.FIRMWARE_SCREEN_DELAY)
        self.servo.lid_close()


    def wait_longer_fw_screen_and_close_lid(self):
        """Wait for firmware screen without timeout and close lid."""
        time.sleep(self.FIRMWARE_SCREEN_DELAY)
        self.wait_fw_screen_and_close_lid()


    def setup_tried_fwb(self, tried_fwb):
        """Setup for fw B tried state.

        It makes sure the system in the requested fw B tried state. If not, it
        tries to do so.

        Args:
          tried_fwb: True if requested in tried_fwb=1; False if tried_fwb=0.
        """
        if tried_fwb:
            if not self.crossystem_checker({'tried_fwb': '1'}):
                logging.info(
                    'Firmware is not booted with tried_fwb. Reboot into it.')
                self.run_faft_step({
                    'userspace_action': self.faft_client.set_try_fw_b,
                })
        else:
            if not self.crossystem_checker({'tried_fwb': '0'}):
                logging.info(
                    'Firmware is booted with tried_fwb. Reboot to clear.')
                self.run_faft_step({})


    def enable_rec_mode_and_reboot(self):
        """Switch to rec mode and reboot.

        This method emulates the behavior of the old physical recovery switch,
        i.e. switch ON + reboot + switch OFF, and the new keyboard controlled
        recovery mode, i.e. just press Power + Esc + Refresh.
        """
        if self._customized_rec_reboot_command:
            logging.info('running the customized rec reboot command')
            os.system(self._customized_rec_reboot_command)
        elif self.client_attr.chrome_ec:
            # Cold reset to clear EC_IN_RW signal
            self.servo.set('cold_reset', 'on')
            time.sleep(self.COLD_RESET_DELAY)
            self.servo.set('cold_reset', 'off')
            time.sleep(self.EC_BOOT_DELAY)
            self.send_uart_command("reboot ap-off")
            time.sleep(self.EC_BOOT_DELAY)
            self.send_uart_command("hostevent set 0x4000")
            self.servo.power_short_press()
        else:
            self.servo.enable_recovery_mode()
            self.cold_reboot()
            time.sleep(self.EC_REBOOT_DELAY)
            self.servo.disable_recovery_mode()


    def enable_dev_mode_and_reboot(self):
        """Switch to developer mode and reboot."""
        if self.client_attr.keyboard_dev:
            self.enable_keyboard_dev_mode()
        else:
            self.servo.enable_development_mode()
            self.faft_client.run_shell_command(
                    'chromeos-firmwareupdate --mode todev && reboot')


    def enable_normal_mode_and_reboot(self):
        """Switch to normal mode and reboot."""
        if self.client_attr.keyboard_dev:
            self.disable_keyboard_dev_mode()
        else:
            self.servo.disable_development_mode()
            self.faft_client.run_shell_command(
                    'chromeos-firmwareupdate --mode tonormal && reboot')


    def wait_fw_screen_and_switch_keyboard_dev_mode(self, dev):
        """Wait for firmware screen and then switch into or out of dev mode.

        Args:
          dev: True if switching into dev mode. Otherwise, False.
        """
        time.sleep(self.FIRMWARE_SCREEN_DELAY)
        if dev:
            self.send_ctrl_d_to_dut()
        else:
            self.send_enter_to_dut()
        time.sleep(self.FIRMWARE_SCREEN_DELAY)
        self.send_enter_to_dut()


    def enable_keyboard_dev_mode(self):
        logging.info("Enabling keyboard controlled developer mode")
        # Plug out USB disk for preventing recovery boot without warning
        self.servo.set('usb_mux_sel1', 'servo_sees_usbkey')
        # Rebooting EC with rec mode on. Should power on AP.
        self.enable_rec_mode_and_reboot()
        self.wait_for_client_offline()
        self.wait_fw_screen_and_switch_keyboard_dev_mode(dev=True)


    def disable_keyboard_dev_mode(self):
        logging.info("Disabling keyboard controlled developer mode")
        if not self.client_attr.chrome_ec:
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
            'firmware_action': (self.wait_fw_screen_and_ctrl_d if dev_mode
                                else None),
        })
        if dev_mode:
            if (not self.client_attr.keyboard_dev and
                not self.crossystem_checker({'devsw_cur': '1'})):
                logging.info('Dev switch is not on. Now switch it on.')
                self.servo.enable_development_mode()
            if not self.crossystem_checker({'devsw_boot': '1',
                    'mainfw_type': 'developer'}):
                logging.info('System is not in dev mode. Reboot into it.')
                self.run_faft_step({
                    'userspace_action': None if self.client_attr.keyboard_dev
                        else (self.faft_client.run_shell_command,
                        'chromeos-firmwareupdate --mode todev && reboot'),
                    'reboot_action': self.enable_keyboard_dev_mode if
                        self.client_attr.keyboard_dev else None,
                })
        else:
            if (not self.client_attr.keyboard_dev and
                not self.crossystem_checker({'devsw_cur': '0'})):
                logging.info('Dev switch is not off. Now switch it off.')
                self.servo.disable_development_mode()
            if not self.crossystem_checker({'devsw_boot': '0',
                    'mainfw_type': 'normal'}):
                logging.info('System is not in normal mode. Reboot into it.')
                self.run_faft_step({
                    'userspace_action': None if self.client_attr.keyboard_dev
                        else (self.faft_client.run_shell_command,
                        'chromeos-firmwareupdate --mode tonormal && reboot'),
                    'reboot_action': self.disable_keyboard_dev_mode if
                        self.client_attr.keyboard_dev else None,
                })


    def setup_kernel(self, part):
        """Setup for kernel test.

        It makes sure both kernel A and B bootable and the current boot is
        the requested kernel part.

        Args:
          part: A string of kernel partition number or 'a'/'b'.
        """
        self.ensure_kernel_boot(part)
        if self.faft_client.diff_kernel_a_b():
            self.copy_kernel_and_rootfs(from_part=part,
                                        to_part=self.OTHER_KERNEL_MAP[part])
        self.reset_and_prioritize_kernel(part)


    def reset_and_prioritize_kernel(self, part):
        """Make the requested partition highest priority.

        This function also reset kerenl A and B to bootable.

        Args:
          part: A string of partition number to be prioritized.
        """
        root_dev = self.faft_client.get_root_dev()
        # Reset kernel A and B to bootable.
        self.faft_client.run_shell_command('cgpt add -i%s -P1 -S1 -T0 %s' %
                (self.KERNEL_MAP['a'], root_dev))
        self.faft_client.run_shell_command('cgpt add -i%s -P1 -S1 -T0 %s' %
                (self.KERNEL_MAP['b'], root_dev))
        # Set kernel part highest priority.
        self.faft_client.run_shell_command('cgpt prioritize -i%s %s' %
                (self.KERNEL_MAP[part], root_dev))
        # Safer to sync and wait until the cgpt status written to the disk.
        self.faft_client.run_shell_command('sync')
        time.sleep(self.SYNC_DELAY)


    def warm_reboot(self):
        """Request a warm reboot.

        A wrapper for underlying servo warm reset.
        """
        # Use cold reset if the warm reset is broken.
        if self.client_attr.broken_warm_reset:
            logging.info('broken_warm_reset is True. Cold rebooting instead.')
            self.cold_reboot()
        else:
            self.servo.warm_reset()


    def cold_reboot(self):
        """Request a cold reboot.

        A wrapper for underlying servo cold reset.
        """
        if self.client_attr.platform == 'Parrot':
            self.servo.set('pwr_button', 'press')
            self.servo.set('cold_reset', 'on')
            self.servo.set('cold_reset', 'off')
            time.sleep(self.POWER_BTN_DELAY)
            self.servo.set('pwr_button', 'release')
        elif self.check_ec_capability(suppress_warning=True):
            # We don't use servo.cold_reset() here because software sync is
            # not yet finished, and device may or may not come up after cold
            # reset. Pressing power button before firmware comes up solves this.
            #
            # The correct behavior should be (not work now):
            #  - If rebooting EC with rec mode on, power on AP and it boots
            #    into recovery mode.
            #  - If rebooting EC with rec mode off, power on AP for software
            #    sync. Then AP checks if lid open or not. If lid open, continue;
            #    otherwise, shut AP down and need servo for a power button
            #    press.
            self.servo.set('cold_reset', 'on')
            self.servo.set('cold_reset', 'off')
            time.sleep(self.POWER_BTN_DELAY)
            self.servo.power_short_press()
        else:
            self.servo.cold_reset()


    def sync_and_warm_reboot(self):
        """Request the client sync and do a warm reboot.

        This is the default reboot action on FAFT.
        """
        self.faft_client.run_shell_command('sync')
        time.sleep(self.SYNC_DELAY)
        self.warm_reboot()


    def sync_and_cold_reboot(self):
        """Request the client sync and do a cold reboot.

        This reboot action is used to reset EC for recovery mode.
        """
        self.faft_client.run_shell_command('sync')
        time.sleep(self.SYNC_DELAY)
        self.cold_reboot()


    def sync_and_ec_reboot(self, args=''):
        """Request the client sync and do a EC triggered reboot.

        Args:
          args: Arguments passed to "ectool reboot_ec". Including:
                  RO: jump to EC RO firmware.
                  RW: jump to EC RW firmware.
                  cold: Cold/hard reboot.
        """
        self.faft_client.run_shell_command('sync')
        time.sleep(self.SYNC_DELAY)
        # Since EC reboot happens immediately, delay before actual reboot to
        # allow FAFT client returning.
        self.faft_client.run_shell_command('(sleep %d; ectool reboot_ec %s)&' %
                                           (self.EC_REBOOT_DELAY, args))
        time.sleep(self.EC_REBOOT_DELAY)
        self.check_lid_and_power_on()


    def full_power_off_and_on(self):
        """Shutdown the device by pressing power button and power on again."""
        # Press power button to trigger Chrome OS normal shutdown process.
        self.servo.power_normal_press()
        time.sleep(self.FULL_POWER_OFF_DELAY)
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
            time.sleep(self.SOFTWARE_SYNC_DELAY)
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
        current_magic = utils.system_output(read_cmd)
        if current_magic == to_magic:
            logging.info("The kernel magic is already %s." % current_magic)
            return
        if current_magic != from_magic:
            raise error.TestError("Invalid kernel image on USB: wrong magic.")

        logging.info('Modify the kernel magic in USB, from %s to %s.' %
                     (from_magic, to_magic))
        write_cmd = ("echo -n '%s' | sudo dd of=%s oflag=sync conv=notrunc "
                     " 2>/dev/null" % (to_magic, kernel_part))
        utils.system(write_cmd)

        if utils.system_output(read_cmd) != to_magic:
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
          check_status: Check the return value of action function. If not
                        succeed, raises a TestFail exception.

        Returns:
          The result value of the action function.

        Raises:
          error.TestError: An error when the action function is not callable.
          error.TestFail: When check_status=True, action function not succeed.
        """
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
                error_msg = action

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
            post_power_action=None):
        """Run shutdown_action(), which makes DUT shutdown, and power it on.

        Args:
          shutdown_action: a function which makes DUT shutdown, like pressing
                           power key.
          pre_power_action: a function which is called before next power on.
          post_power_action: a function which is called after next power on.

        Raises:
          error.TestFail: if the shutdown_action() failed to turn DUT off.
        """
        self._call_action(shutdown_action)
        logging.info('Wait to ensure DUT shut down...')
        try:
            self.wait_for_client()
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


    def run_faft_step(self, step, no_reboot=False):
        """Run a single FAFT step.

        Any missing field falls back to faft_template. An empty step means
        running the default faft_template.

        Args:
          step: A FAFT_STEP dict.
          no_reboot: True to prevent running reboot_action and firmware_action.

        Raises:
          error.TestError: An error when the given step is not valid.
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

        self._call_action(test['userspace_action'])

        # Don't run reboot_action and firmware_action if no_reboot is True.
        if not no_reboot:
            self._call_action(test['reboot_action'])
            self.wait_for_client_offline()
            self._call_action(test['firmware_action'])

            try:
                if 'install_deps_after_boot' in test:
                    self.wait_for_client(
                            install_deps=test['install_deps_after_boot'])
                else:
                    self.wait_for_client()
            except AssertionError:
                logging.info('wait_for_client() timed out.')
                self.reset_client()
                raise


    def run_faft_sequence(self):
        """Run FAFT sequence which was previously registered."""
        sequence = self._faft_sequence
        index = 1
        for step in sequence:
            logging.info('======== Running FAFT sequence step %d ========' %
                         index)
            # Don't reboot in the last step.
            self.run_faft_step(step, no_reboot=(step is sequence[-1]))
            index += 1


    def get_file_from_dut(self, file_list):
        """Get multiple files from client.

        Args:
            file_list: a list with format [(remote_path, host_path), ...]
        """
        for remote_path, host_path in file_list:
            self._client.get_file(remote_path, host_path)


    def send_file_to_dut(self, file_list):
        """Send multiple files from client.

        Args:
            file_list: a list with format [(host_path, remote_path), ...]
        """
        for host_path, remote_path in file_list:
            self._client.send_file(host_path, remote_path)


    def get_current_firmware_sha(self):
        """Get current firmware sha of body and vblock.

        Returns:
            Current firmware sha follows the order (
                vblock_a_sha, body_a_sha, vblock_b_sha, body_b_sha)
        """
        current_firmware_sha = (self.faft_client.get_firmware_sig_sha('a'),
                                self.faft_client.get_firmware_sha('a'),
                                self.faft_client.get_firmware_sig_sha('b'),
                                self.faft_client.get_firmware_sha('b'))
        return current_firmware_sha


    def create_backup_file_list(self, files,
                                src_dir, src_suffix,
                                dst_dir, dst_suffix):
        """Create a file list to transfer.

        [('src_dir/file.src_suffix', 'dst_dir/file.dst_suffix'), ...]

        Args:
            files: a tuple of file's name
            src_dir: source directory
            src_suffix: files in src_dir with suffix
            dst_dir: destination directory
            dst_suffix: files in dst_dir with suffix

        Returns:
            A file list.
        """

        file_list = []
        for file_name in self._backup_firmware_name:
            file_list.append((os.path.join(src_dir, file_name + src_suffix),
                              os.path.join(dst_dir, file_name + dst_suffix)))
        return file_list


    def is_firmware_changed(self):
        """Check if the current firmware changed, by comparing its SHA.

        Returns:
            True if it is changed, otherwise Flase.
        """
        # Device may not be rebooted after test.
        self.faft_client.reload_firmware()

        current_sha = self.get_current_firmware_sha()

        if current_sha == self._backup_firmware_sha:
            return False
        else:
            corrupt_VBOOTA = (current_sha[0] != self._backup_firmware_sha[0])
            corrupt_FVMAIN = (current_sha[1] != self._backup_firmware_sha[1])
            corrupt_VBOOTB = (current_sha[2] != self._backup_firmware_sha[2])
            corrupt_FVMAINB = (current_sha[3] != self._backup_firmware_sha[3])
            logging.info("Firmware changed:")
            logging.info('VBOOTA is changed: %s' % corrupt_VBOOTA)
            logging.info('VBOOTB is changed: %s' % corrupt_VBOOTB)
            logging.info('FVMAIN is changed: %s' % corrupt_FVMAIN)
            logging.info('FVMAINB is changed: %s' % corrupt_FVMAINB)
            return True


    def backup_firmware(self, suffix='.original'):
        """Backup firmware to file, and then send it to host.

        Args:
            suffix: a string appended to backup file name
        """
        remote_temp_dir = self.faft_client.create_temp_dir()
        self.faft_client.dump_firmware_rw(remote_temp_dir)

        file_list = self.create_backup_file_list(self._backup_firmware_name,
                                            remote_temp_dir, '',
                                            self.resultsdir, suffix)
        self.get_file_from_dut(file_list)

        self._backup_firmware_sha = self.get_current_firmware_sha()
        logging.info('Backup firmware stored in %s with suffix %s' % (
            self.resultsdir, suffix))


    def is_firmware_saved(self):
        """Check if a firmware saved (called backup_firmware before).

        Returns:
            True if the firmware is backuped; otherwise False.
        """
        return self._backup_firmware_sha != ()


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
        remote_temp_dir = self.faft_client.create_temp_dir()
        file_list = self.create_backup_file_list(self._backup_firmware_name,
                                                 self.resultsdir, suffix,
                                                 remote_temp_dir, '')
        self.send_file_to_dut(file_list)

        self.faft_client.write_firmware_rw(remote_temp_dir)
        self.sync_and_warm_reboot()
        self.wait_for_client_offline()
        self.wait_for_client()

        logging.info('Successfully restore firmware.')
