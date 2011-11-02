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
from autotest_lib.server.cros.servotest import ServoTest


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
        usb_dev = self.probe_host_usb_dev()
        if not usb_dev:
            raise error.TestError(
                    'An USB disk should be plugged in the servo board.')

        tmp_dir = tempfile.mkdtemp()
        utils.system('sudo mount -r %s3 %s' % (usb_dev, tmp_dir))
        code = utils.system('grep -q "Test Build" %s/etc/lsb-release' %
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


    def run_faft_sequence(self):
        """Run FAFT sequence.

        Raises:
            error.TestFail: An error when the test failed.
        """
        default_test = self._faft_template
        sequence = self._faft_sequence

        for test in sequence:
            cur_test = {}
            cur_test.update(default_test)
            cur_test.update(test)

            if cur_test['state_checker']:
                if not self._call_action(cur_test['state_checker']):
                    raise error.TestFail('State checker failed!')

            self._call_action(cur_test['userspace_action'])

            # Don't run reboot_action and firmware_action of the last step.
            if test is not sequence[-1]:
                self._call_action(cur_test['reboot_action'])
                self.wait_for_client_offline()
                self._call_action(cur_test['firmware_action'])

                if 'install_deps_after_boot' in cur_test:
                    self.wait_for_client(
                            install_deps=cur_test['install_deps_after_boot'])
                else:
                    self.wait_for_client()
