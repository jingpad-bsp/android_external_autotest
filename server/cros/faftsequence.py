# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

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
    FIRMWARE_SCREEN_DELAY = 2
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
    # Delay between EC reboot and pressing power button
    POWER_BTN_DELAY = 0.5
    # Delay between sending keystroke to firmware
    FIRMWARE_KEY_DELAY = 0.5

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

    _faft_template = {}
    _faft_sequence = ()

    _customized_ctrl_d_key_command = None
    _customized_enter_key_command = None
    _install_image_path = None
    _firmware_update = False


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


    def setup(self):
        """Autotest setup function."""
        super(FAFTSequence, self).setup()
        if not self._remote_infos['faft']['used']:
            raise error.TestError('The use_faft flag should be enabled.')
        self.clear_gbb_flags(self.GBB_FLAG_FORCE_DEV_SWITCH_ON)
        self.register_faft_template({
            'state_checker': (None),
            'userspace_action': (None),
            'reboot_action': (self.sync_and_warm_reboot),
            'firmware_action': (None)
        })
        if self._install_image_path:
            self.install_test_image(self._install_image_path,
                                    self._firmware_update)


    def cleanup(self):
        """Autotest cleanup function."""
        self._faft_sequence = ()
        self._faft_template = {}
        super(FAFTSequence, self).cleanup()


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
            self.servo.set('usb_mux_sel1', 'servo_sees_usbkey')
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
        recovery mode. Then runs 'chromeos-install' to install it to DUT disk.

        Args:
            image_path: Path on the host to the test image.
            firmware_update: Also update the firmware after installing.
        """
        install_cmd = 'chromeos-install --yes'
        if firmware_update:
            install_cmd += ' && chromeos-firmwareupdate --mode recovery'
        build_ver, build_hash = lab_test.VerifyImageAndGetId(cros_dir,
                                                             image_path)
        logging.info('Processing build: %s %s' % (build_ver, build_hash))

        # Reuse the install_recovery_image method by using a test image.
        # Don't wait for completion but run chromeos-install to install it.
        self.servo.install_recovery_image(image_path)
        self.wait_for_client(install_deps=True)
        self.run_faft_step({
            'userspace_action': (self.faft_client.run_shell_command,
                                 install_cmd)
        })


    def clear_gbb_flags(self, mask):
        """Clear the GBB flags in the current flashrom.

        Args:
          mask: A mask of flags to be cleared.
        """
        gbb_flags = self.faft_client.get_gbb_flags()
        if (gbb_flags & mask):
            logging.info('Clear the GBB flags of 0x%x, from 0x%x to 0x%x.' %
                         (mask, gbb_flags, gbb_flags ^ mask))
            self.faft_client.run_shell_command(
                    '/usr/share/vboot/bin/set_gbb_flags.sh 0x%x' %
                    (gbb_flags ^ mask))


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


    def check_ec_capability(self, required_cap=[]):
        """Check if current platform has required EC capabilities.

        Args:
          required_cap: A list containing required EC capabilities. Pass in
            None to only check for presence of Chrome EC.

        Returns:
          True if requirements are met. Otherwise, False.
        """
        if not self.client_attr.chrome_ec:
            logging.warn('Requires Chrome EC to run this test.')
            return False

        for cap in required_cap:
            if cap not in self.client_attr.ec_capability:
                logging.warn('Requires EC capability "%s" to run this test.' %
                             cap)
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
                    'recoverysw_boot': '0',
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
            self.copy_kernel_and_rootfs(from_part=self.OTHER_KERNEL_MAP[part],
                                        to_part=part)
            self.run_faft_step({
                'userspace_action': (self.reset_and_prioritize_kernel, part),
            })


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


    def wait_fw_screen_and_plug_usb(self):
        """Wait for firmware warning screen and then unplug and plug the USB."""
        time.sleep(self.USB_LOAD_DELAY)
        self.servo.set('usb_mux_sel1', 'servo_sees_usbkey')
        time.sleep(self.USB_PLUG_DELAY)
        self.servo.set('usb_mux_sel1', 'dut_sees_usbkey')


    def wait_fw_screen_and_press_power(self):
        """Wait for firmware warning screen and press power button."""
        time.sleep(self.FIRMWARE_SCREEN_DELAY)
        self.servo.power_short_press()


    def wait_fw_screen_and_close_lid(self):
        """Wait for firmware warning screen and close lid."""
        time.sleep(self.FIRMWARE_SCREEN_DELAY)
        self.servo.lid_close()


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


    def enable_dev_mode_and_fw(self):
        """Enable developer mode and use developer firmware."""
        if self.client_attr.keyboard_dev:
            self.enable_keyboard_dev_mode()
        else:
            self.servo.enable_development_mode()
            self.faft_client.run_shell_command(
                    'chromeos-firmwareupdate --mode todev && reboot')


    def enable_normal_mode_and_fw(self):
        """Enable normal mode and use normal firmware."""
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
        time.sleep(self.FIRMWARE_KEY_DELAY)
        self.send_enter_to_dut()


    def enable_keyboard_dev_mode(self):
        logging.info("Enabling keyboard controlled developer mode")
        # Plug out USB disk for preventing recovery boot without warning
        self.servo.set('usb_mux_sel1', 'servo_sees_usbkey')
        # Rebooting EC with rec mode on. Should power on AP.
        self.servo.enable_recovery_mode()
        self.servo.cold_reset()
        self.wait_fw_screen_and_switch_keyboard_dev_mode(dev=True)
        self.servo.disable_recovery_mode()


    def disable_keyboard_dev_mode(self):
        logging.info("Disabling keyboard controlled developer mode")
        self.servo.disable_recovery_mode()
        # We don't use servo.cold_reset() here because software sync is not yet
        # finished, and device may or may not come up after cold reset. Pressing
        # power button before firmware comes up solves this.
        self.servo.set('cold_reset', 'on')
        self.servo.set('cold_reset', 'off')
        # Rebooting EC with rec mode off. Software sync should power on AP,
        # and then shut down AP after a while.
        # TODO(victoryang): Figure out the proper delay period before pressing
        #                   power button after software sync is done.
        time.sleep(self.POWER_BTN_DELAY)
        self.servo.power_short_press()
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


    def sync_and_warm_reboot(self):
        """Request the client sync and do a warm reboot.

        This is the default reboot action on FAFT.
        """
        self.faft_client.run_shell_command('sync')
        time.sleep(self.SYNC_DELAY)
        self.servo.warm_reset()


    def sync_and_cold_reboot(self):
        """Request the client sync and do a cold reboot.

        This reboot action is used to reset EC for recovery mode.
        """
        self.faft_client.run_shell_command('sync')
        time.sleep(self.SYNC_DELAY)
        self.servo.cold_reset()


    def sync_and_ec_reboot(self):
        """Request the client sync and do a EC triggered reboot."""
        self.faft_client.run_shell_command('sync')
        time.sleep(self.SYNC_DELAY)
        self.faft_client.run_shell_command('(sleep %d; ectool reboot_ec)&' %
                                           self.EC_REBOOT_DELAY)
        time.sleep(self.EC_REBOOT_DELAY + self.POWER_BTN_DELAY)
        self.servo.power_normal_press()


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


    def _call_action(self, action_tuple):
        """Call the action function with/without arguments.

        Args:
          action_tuple: A function, or a tuple which consisted of a function
              and its arguments (if any).

        Returns:
          The result value of the action function.
        """
        if isinstance(action_tuple, tuple):
            action = action_tuple[0]
            args = action_tuple[1:]
            if callable(action):
                logging.info('calling %s with parameter %s' % (
                        str(action), str(action_tuple[1])))
                return action(*args)
            else:
                logging.info('action is not callable!')
        else:
            action = action_tuple
            if action is not None:
                if callable(action):
                    logging.info('calling %s' % str(action))
                    return action()
                else:
                    logging.info('action is not callable!')

        return None


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
          error.TestFail: An error when the test failed.
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
            if not self._call_action(test['state_checker']):
                raise error.TestFail('State checker failed!')

        self._call_action(test['userspace_action'])

        # Don't run reboot_action and firmware_action if no_reboot is True.
        if not no_reboot:
            self._call_action(test['reboot_action'])
            self.wait_for_client_offline()
            self._call_action(test['firmware_action'])

            if 'install_deps_after_boot' in test:
                self.wait_for_client(
                        install_deps=test['install_deps_after_boot'])
            else:
                self.wait_for_client()


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
