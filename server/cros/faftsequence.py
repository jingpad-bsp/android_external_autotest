# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re
import tempfile
import time
import xmlrpclib

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
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
        reboot_action: a function to do reboot, default: sync_and_hw_reboot.
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
    """
    version = 1


    # Mapping of partition number of kernel and rootfs.
    KERNEL_MAP = {'a':'2', 'b':'4', '2':'2', '4':'4', '3':'2', '5':'4'}
    ROOTFS_MAP = {'a':'3', 'b':'5', '2':'3', '4':'5', '3':'3', '5':'5'}
    OTHER_KERNEL_MAP = {'a':'4', 'b':'2', '2':'4', '4':'2', '3':'4', '5':'2'}
    OTHER_ROOTFS_MAP = {'a':'5', 'b':'3', '2':'5', '4':'3', '3':'5', '5':'3'}

    # Delay timing
    FIRMWARE_SCREEN_DELAY = 10
    TEXT_SCREEN_DELAY = 20
    USB_PLUG_DELAY = 10

    _faft_template = None
    _faft_sequence = ()


    def setup(self):
        """Autotest setup function."""
        super(FAFTSequence, self).setup()
        if not self._remote_infos['faft']['used']:
            raise error.TestError('The use_faft flag should be enabled.')
        self.register_faft_template({
            'state_checker': (None),
            'userspace_action': (None),
            'reboot_action': (self.sync_and_hw_reboot),
            'firmware_action': (None)
        })


    def cleanup(self):
        """Autotest cleanup function."""
        self._faft_sequence = ()
        self._faft_template = None
        super(FAFTSequence, self).cleanup()


    def assert_test_image_in_usb_disk(self):
        """Assert an USB disk plugged-in on servo and a test image inside.

        Raises:
          error.TestError: if USB disk not detected or not a test image.
        """
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
        part = self.faft_client.get_root_part()
        return self.ROOTFS_MAP[expected_part] == part[-1]


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


    def wait_fw_screen_and_ctrl_d(self):
        """Wait for firmware warning screen and press Ctrl-D."""
        time.sleep(self.FIRMWARE_SCREEN_DELAY)
        self.servo.ctrl_d()


    def wait_fw_screen_and_plug_usb(self):
        """Wait for firmware warning screen and then unplug and plug the USB."""
        time.sleep(self.FIRMWARE_SCREEN_DELAY)
        self.servo.set('usb_mux_sel1', 'servo_sees_usbkey')
        time.sleep(self.USB_PLUG_DELAY)
        self.servo.set('usb_mux_sel1', 'dut_sees_usbkey')


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


    def setup_dev_mode(self, dev_mode):
        """Setup for development mode.

        It makes sure the system in the requested normal/dev mode. If not, it
        tries to do so.

        Args:
          dev_mode: True if requested in dev mode; False if normal mode.
        """
        # Change the default firmware_action for dev mode passing the fw screen.
        self.register_faft_template({
            'state_checker': (None),
            'userspace_action': (None),
            'reboot_action': (self.sync_and_hw_reboot),
            'firmware_action': (self.wait_fw_screen_and_ctrl_d if dev_mode
                                else None),
        })
        if dev_mode:
            if not self.crossystem_checker({'devsw_cur': '1'}):
                logging.info('Dev switch is not on. Now switch it on.')
                self.servo.enable_development_mode()
            if not self.crossystem_checker({'devsw_boot': '1',
                    'mainfw_type': 'developer'}):
                logging.info('System is not in dev mode. Reboot into it.')
                self.run_faft_step({
                    'userspace_action': (self.faft_client.run_shell_command,
                        'chromeos-firmwareupdate --mode todev && reboot'),
                    'reboot_action': None,
                })
        else:
            if not self.crossystem_checker({'devsw_cur': '0'}):
                logging.info('Dev switch is not off. Now switch it off.')
                self.servo.disable_development_mode()
            if not self.crossystem_checker({'devsw_boot': '0',
                    'mainfw_type': 'normal'}):
                logging.info('System is not in normal mode. Reboot into it.')
                self.run_faft_step({
                    'userspace_action': (self.faft_client.run_shell_command,
                        'chromeos-firmwareupdate --mode tonormal && reboot'),
                    'reboot_action': None,
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


    def sync_and_hw_reboot(self):
        """Request the client sync and do a warm reboot.

        This is the default reboot action on FAFT.
        """
        self.faft_client.run_shell_command('sync')
        time.sleep(5)
        self.servo.warm_reset()


    def _str_action(self, action):
        """Convert the action function into a readable string.

        The simple str() doesn't work on remote objects since we disable
        allow_dotted_names flag when we launch the SimpleXMLRPCServer.
        So this function handles the exception in this case.

        Args:
          action: A function.

        Returns:
          A readable string.
        """
        try:
            return str(action)
        except xmlrpclib.Fault:
            return '<remote method>'


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
                        self._str_action(action), str(action_tuple[1])))
                return action(*args)
            else:
                logging.info('action is not callable!')
        else:
            action = action_tuple
            if action is not None:
                if callable(action):
                    logging.info('calling %s' % self._str_action(action))
                    return action()
                else:
                    logging.info('action is not callable!')

        return None


    def register_faft_template(self, template):
        """Register FAFT template, the default FAFT_STEP of each step.

        Args:
          template: A FAFT_STEP dict.
        """
        self._faft_template = template


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
        """
        test = {}
        test.update(self._faft_template)
        test.update(step)

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
        for step in sequence:
            # Don't reboot in the last step.
            self.run_faft_step(step, no_reboot=(step is sequence[-1]))
