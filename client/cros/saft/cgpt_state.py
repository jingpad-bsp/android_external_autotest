# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""CGPT state machine for cgpt tests"""

import os
import sys

import cgpt_handler


# cgpt test state step number is stored in this file
STEP_FILE = 'cgpt_test_step'


# CGPT_STATE_SEQ represents a sequence of test steps used to
# controll the SAFT cgpt state machine.
#
# cgpt test_loop() is the entry function from saft_utility.py to
# execute cgpt tests
#
# There are three elements in a test state tuple:
#   (action_kern_props, expected_kern_props, expected_boot_vector),
#      where action_kern_props:   (kern_prop_a, kern_prop_b)
#            expected_kern_props: (kern_prop_a, kern_prop_b)
#                  kern_prop_a|b: 'priority:tries:successful'
#            expected_boot_vector: e.g., '1:1:1:0:3'
#
#   An example cpgt test state tuple looks like
#   (('7:0:1', '10:5:0'), ('7:0:1', '10:4:0'), '1:1:0:0:5'),
#
# CGPT_STATE_SEQ can be one of the following choices
#   MANUAL: needs manual operation to handle recovery boot.
#   AUTO: all steps can be executed automatically without manual operations.
#   COMPLETE: MANUAL + AUTL
#   SHORT: a short list of AUTO test steps for development purpose only
#
# ToDo (josephsih): the CGPT state sequence data can be moved to a data
#                   file for easier editing without touching the code

# This cgpt state sequence specifies the steps requiring manual operations.
CGPT_STATE_SEQ_MANUAL = (
    # Both kernels have tries set to zero and none is successful => recovery.
    # Note: this particular cgpt test must be followed by other normal
    #       cgpt_tests. Otherwise, it will always boot into the recovery mode.
    (('6:0:0', '7:0:0'),   ('6:0:0', '7:0:0'),   '6:0:*:1:3'),
    # KERN-A with successful bit and higher priority has precedence.
    (('3:0:1', '2:15:0'),  ('3:0:1', '2:15:0'),  '1:1:*:0:3'),
    )

# This cgpt state sequence specifies the steps executed automatically.
CGPT_STATE_SEQ_AUTO = (
    # KERN-A with successful bit but lower priority. KERN-B has precedence.
    (('7:0:1', '10:5:0'),  ('7:0:1', '10:4:0'),  '1:1:*:0:5'),
    # KERN-B with successful bit but lower priority. KERN-A has precedence.
    (('12:13:0', '9:0:1'), ('12:12:0', '9:0:1'), '1:1:*:0:3'),
    # KERN-A with successful bit and higher priority has precedence.
    (('3:0:1', '2:15:0'),  ('3:0:1', '2:15:0'),  '1:1:*:0:3'),
    # KERN-B with successful bit and higher priority has precedence.
    (('3:5:0', '4:0:1'),   ('3:5:0', '4:0:1'),   '1:1:*:0:5'),
    # KERN-A with higher priority and non-zero tries has precedence.
    (('6:12:0', '3:14:0'), ('6:11:0', '3:14:0'), '1:1:*:0:3'),
    # KERN-B with higher priority and non-zero tries has precedence.
    (('5:13:0', '9:8:0'),  ('5:13:0', '9:7:0'),  '1:1:*:0:5'),
    # KERN-A with higher priority but zero tries has no precedence.
    (('9:0:0', '7:10:0'),  ('9:0:0', '7:9:0'),   '1:1:*:0:5'),
    # KERN-B with higher priority but zero tries has no precedence.
    (('6:13:0', '7:0:0'),  ('6:12:0', '7:0:0'),  '1:1:*:0:3'),
    # Both kernels are successful. KERN-B with higher priority has precedence.
    (('8:0:1', '9:0:1'),   ('8:0:1', '9:0:1'),   '1:1:*:0:5'),
    # Both kernels are successful. KERN-A with higher priority has precedence.
    (('8:0:1', '7:0:1'),   ('8:0:1', '7:0:1'),   '1:1:*:0:3'),
    )

# This cgpt state sequence only specifies limited steps for test.
# This is used only during development.
CGPT_STATE_SEQ_SHORT = (
    # KERN-A with successful bit but lower priority. KERN-B has precedence.
    (('7:0:1', '10:5:0'),  ('7:0:1', '10:4:0'),  '1:1:*:0:5'),
    # KERN-B with successful bit but lower priority. KERN-A has precedence.
    (('12:13:0', '9:0:1'), ('12:12:0', '9:0:1'), '1:1:*:0:3'),
    )

# A complete sequence is equal to manual sequence + auto sequence
CGPT_STATE_SEQ_COMPLETE = CGPT_STATE_SEQ_MANUAL + CGPT_STATE_SEQ_AUTO

# The END should be the suffix of any cgpt state seq body.
# This is the tuple handling ending boundary condition. With this
# step, we are thus able to check the rebooting behavior of the
# previous step. Also we can set any cgpt parameters we would like the
# machine to keep before leaving cgpt tests.
CGPT_STATE_SEQ_END = (
    (('3:0:1', '2:5:0'),  ('3:0:1', '2:5:0'),  '1:1:*:0:3'),
    )

# A test state sequence body dictionary
CGPT_STATE_SEQ_BODY = {'MANUAL':CGPT_STATE_SEQ_MANUAL,
                       'AUTO':CGPT_STATE_SEQ_AUTO,
                       'COMPLETE':CGPT_STATE_SEQ_COMPLETE,
                       'SHORT':CGPT_STATE_SEQ_SHORT
                      }


class CgptStateError(Exception):
    pass


class CgptState:
    """A class to encapsulate cgpt test operations and its test state tuples"""

    DELIMIT = ':'
    KERN_NAME = ['KERN-A', 'KERN-B']
    PROP_NAME = ['priority', 'tries' , 'successful']
    PARA_POS = {'ACTION':0, 'EXPECTED':1, 'BOOT_VEC':2}

    def __init__(self, choice, chros_if, base_storage_dev):
        """Initializer: read CGPT_STATE_SEQ

        cgpt_state_seq - a sequence of tuples by which to carry on cgpt tests

        num_steps - the number of steps (tuples) to carry on cgpt tests

        base_storage_device - the base device to invoke chromeos_interface

        chros_if - an object providing services manipulating kernel images.

        cgpth: an object providing services manipulating gpt information

        step_file: a file recording current step number
        """
        self.cgpt_state_seq = CGPT_STATE_SEQ_BODY[choice] + CGPT_STATE_SEQ_END
        self.num_steps = len(self.cgpt_state_seq)
        self.base_storage_dev = base_storage_dev
        self.chros_if = chros_if
        self.cgpth = cgpt_handler.CgptHandler(self.chros_if)
        self.step_file = None

    def get_step(self):
        """Get the step number of cgpt test"""
        self.step_file = self.chros_if.state_dir_file(STEP_FILE)
        step = int(open(self.step_file, 'r').read().strip())
        self._assert_step(step)
        return step

    def set_step(self, step):
        """Set the step number of cgpt test in a file"""
        self.step_file = self.chros_if.state_dir_file(STEP_FILE)
        with open(self.step_file, 'w') as f:
            f.write('%d' % step)
            f.flush()
            os.fdatasync(f)

    def _is_matched_kern_prop_dict(self, part_prop_dict,
                                   expected_kern_prop_dict):
        """ Compare if kernel properties are the same in both dictionaries

        part_prop_dict - a partition property dictionary retrieved from device
        expected_kern_prop_dict - expected kernel property specified in cgpt
                         state tuple

        """
        if (expected_kern_prop_dict is None):
            return True
        for name in CgptState.PROP_NAME:
            if part_prop_dict[name] != expected_kern_prop_dict[name]:
                return False
        return True

    def _assert_step(self, step):
        """assert that the step number is legal"""
        if step >= self.num_steps or step < 0:
            raise CgptStateError('Error: Wrong step number %d in cgpt_state' %
                                  step)

    def _get_boot_vector(self, step):
        """Read boot vector for a specified step, e.g., '1:1:1:0:3' """
        return self.cgpt_state_seq[step][CgptState.PARA_POS['BOOT_VEC']]

    def _get_kern_props(self, step, para_flag):
        """Read action or expected kernel property tuples based on para_flag

        para_flag - parameter flag determining action or expected property
        Example of returned value: ('8:15:0', '9:15:0')

        """
        para_pos = CgptState.PARA_POS[para_flag]
        return self.cgpt_state_seq[step][para_pos]

    def _str_to_kern_prop_dict(self, kern_prop):
        """Convert a string to kernel property dictionary

        kern_prop - a string of kernel property
        Example: kern_prop = '8:15:0'
                 return {'priority':8, 'tries':15, 'successful':0}

        """
        kern_prop_list = kern_prop.split(CgptState.DELIMIT)
        kern_prop_dict = {}
        for idx, name in enumerate(CgptState.PROP_NAME):
            kern_prop_dict[name] = int(kern_prop_list[idx])
        return kern_prop_dict

    def _get_kern_prop_dict(self, step, para_flag, part):
        """Read single kernel property and build a dictionary for it

        para_flag: parameter flag, can be 'ACTION' or 'EXPECTED'
        part: partition, can be 'KERN-A' or 'KERN-B'
        Example: read '8:15:0', and
                 return {'priority':8, 'tries':15, 'successful':0}.

        """
        kern_props = self._get_kern_props(step, para_flag)
        if kern_props == None:
            return None
        part_index = CgptState.KERN_NAME.index(part)
        kern_prop = kern_props[part_index]
        return self._str_to_kern_prop_dict(kern_prop)

    def _cgpt_test(self, action_kern_props):
        """Set up the cgpt kernel properties"""
        self.cgpth.read_device_info(self.base_storage_dev)
        if action_kern_props is None:
            raise CgptStateError("Error: The action parameter for \
                                  cgpt_state_seq should not be 'None'!")
        # Looping through distinct partitions (KERN-A and KERN-B)
        for index, kern_prop in enumerate(action_kern_props):
            kern_prop_dict = self._str_to_kern_prop_dict(kern_prop)
            self.cgpth.set_partition(self.base_storage_dev,
                                     self.KERN_NAME[index], kern_prop_dict)

    def _check_kern_props(self, step):
        """Check machine kernel properties against cgpt_state_seq

        Check if the machine kernel properties comply with the expected
        kernel properties specified in cgpt_state_seq

        """
        # Read device information from machine
        self.cgpth.read_device_info(self.base_storage_dev)
        # Compare two kernel partitions: KERN-A and KERN-B
        cgpt_kern_prop_flag = True
        for part_name in CgptState.KERN_NAME:
            # get partition properties from machine
            part_prop = self.cgpth.get_partition(self.base_storage_dev,
                                                 part_name)
            # Get expected cpgt kernel properties
            expected_kern_prop = self._get_kern_prop_dict(step, 'EXPECTED',
                                                         part_name)
            if not self._is_matched_kern_prop_dict(part_prop,
                                               expected_kern_prop):
                cgpt_kern_prop_flag = False
                self.chros_if.log('Error (cgpt step %d) %s: Wrong cgpt \
                           kernel property, %s was expected, but got %s' %
                          (step, part_name, expected_kern_prop, part_prop))
            else:
                self.chros_if.log('Cgpt %s: %s was expected and matched.' %
                                  (part_name, expected_kern_prop))
        return cgpt_kern_prop_flag

    def _check_boot_vector(self, step):
        """Check machine boot vecotr against cgpt_state_seq

        Check if machine boot vector complies with the expected boot vecotr
        specified in cgpt_state_seq

        """
        # Get machine boot vector
        boot_vector = self.chros_if.boot_state_vector()
        # Get expected boot vector
        expected_boot_vector = self._get_boot_vector(step)
        matched = self.chros_if.cmp_boot_vector(boot_vector,
                                                expected_boot_vector)
        if not matched:
            self.chros_if.log('Error (cgpt step %d): boot vectors %s and %s \
                 do not match' % (step, boot_vector, expected_boot_vector))
        return matched

    def test_loop(self):
        """Loop through every cgpt test state tuple.

        This is the entry function invoked from FirmwareTest of saft_utility.py
        Return 0 - there are more cgpt tests to execute
               1 - no more cgpt test. Firmware Test can proceed to its own
                   next step

        """
        step = self.get_step()
        self.chros_if.log('Calling cgpt_state.test_loop: step = %d/%d' %
                          (step, self.num_steps))

        # Checking the number of parameters in this cpgt state tuple
        if len(self.cgpt_state_seq[step]) != len(CgptState.PARA_POS):
            err_para_log = 'Error: number of parameters in %s is not correct.'
            raise CgptStateError(err_para_log % self.cgpt_state_seq[step])

        if step > 0:
            # Check cpgt kernel properties for previous step
            cgpt_kern_prop_flag = self._check_kern_props(step-1)
            # Check boot vector for previous step
            boot_vector_flag = self._check_boot_vector(step-1)
            if not (cgpt_kern_prop_flag and boot_vector_flag):
                err_chk_log = 'Error: cgpt property or boot vector at step %d'
                raise CgptStateError(err_chk_log % step)

        # Perform cgpt test action
        action_kern_props = self._get_kern_props(step, 'ACTION')
        self._cgpt_test(action_kern_props)

        # Check if we have finished cgpt state tests
        if step >= self.num_steps-1:
            success_log = 'Finishes cgpt tests successfully at step %d.'
            self.chros_if.log(success_log % step)
            return 1
        else:
            self.set_step(step+1)
            return 0
