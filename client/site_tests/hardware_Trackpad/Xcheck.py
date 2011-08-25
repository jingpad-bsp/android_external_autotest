# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

''' A module verifying whether X events satisfy specified criteria '''

import logging
import time
import utils

import Xevent

from operator import le, ge, eq, lt, gt, ne, and_


class Xcheck:
    ''' Check whether X events observe test criteria '''
    RESULT_STR = {True : 'Pass', False : 'Fail'}

    def __init__(self, dev):
        self.dev = dev
        self.xbutton = Xevent.XButton()
        self.button_labels = self.xbutton.get_supported_buttons()
        # Create a dictionary to look up button label
        #        e.g., {1: 'Button Left', ...}
        self.button_dict = dict(map(lambda b:
                                    (self.xbutton.get_value(b), b),
                                    self.button_labels))
        self._get_boot_time()
        self.xevent = Xevent.XEvent(self.xbutton)
        self.op_dict = {'>=': ge, '<=': le, '==': eq, '=': eq, '>': gt,
                        '<': lt, '!=': ne, '~=': ne, 'not': ne, 'is not': ne}

    def _get_boot_time(self):
        ''' Get the system boot up time

        Boot time can be used to convert the elapsed time since booting up
        to that since Epoch.
        '''
        stat_cmd = 'cat /proc/stat'
        stat = utils.system_output(stat_cmd)
        boot_time_tuple = tuple(int(line.split()[1])
                                for line in stat.splitlines()
                                if line.startswith('btime'))
        if len(boot_time_tuple) == 0:
            raise error.TestError('Fail to extract boot time by "%s"' %
                                  stat_cmd)
        self.boot_time = boot_time_tuple[0]

    def _set_flags(self):
        ''' Set all flags to True before invoking check function '''
        self.motion_flag = True
        self.button_flag = True
        self.seq_flag = True
        self.delay_flag = True

    def _get_result(self):
        ''' Get the final result from various check flags '''
        flags = (self.motion_flag, self.button_flag, self.seq_flag,
                 self.delay_flag)
        self.result = flags[0] if len(flags) == 1 else reduce(and_, flags)
        logging.info('    --> Result: %s' % Xcheck.RESULT_STR[self.result])

    def _compare(self, ops):
        ''' Compare function generator

        Generate a function to compare two sequences using the specified
        operators.
        '''
        return lambda seq1, seq2: reduce(and_, map(lambda op, s1, s2:
                                                   op(s1, s2), ops, seq1, seq2))

    def _motion_criteria(self, motion_crit):
        ''' Extract motion operator and value '''
        if motion_crit is None:
            return (None, None)
        motion_op = self.op_dict[motion_crit[1]]
        motion_value = motion_crit[2]
        return (motion_op, motion_value)

    def _button_criteria(self, button_crit):
        ''' Create a list of button criteria

        button_crit: the criteria of a single specified button
        TODO(josephsih): support a list of button criteria to make it flexible.
        '''
        len_button_labels = len(self.button_labels)
        values = [0] * len_button_labels
        ops = [eq] * len_button_labels
        if button_crit is not None:
            button_label, button_op, button_value = button_crit
            button_index = self.xbutton.get_index(button_label)
            values[button_index] = button_value
            ops[button_index] = self.op_dict[button_op]
        return (ops, values)

    def _insert_nop(self, nop_str):
        ''' Insert a 'NOP' fake event into the xevent_data

        NOP is not an X event. It is inserted to indicate the occurrence of
        related device events.
        '''
        event_dict = {
                '2nd Finger Lifted': (self.dev.get_2nd_finger_lifted_time,
                                      'Motion'),
                'Two Finger Touch': (self.dev.get_two_finger_touch_time_list,
                                     ''),
        }

        result = event_dict.get(nop_str, None)
        if result is None:
            logging.warn('There is no device event method for %s.' % nop_str)
            return

        # TODO(josephsih): Using a class here with named method and property
        # instead of a list would be better.
        dev_event_time = result[0]()
        matching_xevent_name = result[1]
        if dev_event_time is None:
            logging.warn('Cannot get time for %s.' % nop_str)
            return

        if not isinstance(dev_event_time, list):
            dev_event_time = [dev_event_time]

        begin_index = 0
        for devent_time in dev_event_time:
            for index, line in enumerate(self.xevent.xevent_data[begin_index:]):
                xevent_name = line[0]
                xevent_dict = line[1]
                if xevent_name.startswith(matching_xevent_name):
                    xevent_time = float(xevent_dict['time'])
                    if xevent_time > devent_time:
                        insert_index = begin_index + index
                        nop_data = ('NOP', nop_str, devent_time)
                        self.xevent.xevent_data.insert(insert_index, nop_data)
                        begin_index = insert_index + 1
                        break

    def _insert_nop_per_criteria(self, criteria_method):
        ''' Insert NOP based on criteria '''
        for c in criteria_method:
            if self.criteria.has_key(c):
                if c == 'wheel_speed':
                    # There are a couple of times of two-finger scrolling.
                    # Insert NOP between them in self.xevent_seq
                    self._insert_nop('Two Finger Touch')
                elif c == 'sequence':
                    crit_sequence = self.criteria[c]
                    # Insert NOP in self.xevent_seq if NOP is specified
                    # in sequence criteria.
                    # Example of crit_sequence below:
                    #     ('NOP', 'Single Finger Lifted')
                    #     ('NOP', '2nd Finger Lifted')
                    for s in crit_sequence:
                        if s[0] == 'NOP':
                            self._insert_nop(s[1])

    def _get_direction(self):
        directions = ['up', 'down', 'left', 'right']
        file_name = self.gesture_file_name.split('-')[self.func_name_pos]
        for d in directions:
            if d in file_name:
                return d
        return None

    def _get_button_wheel_label_per_direction(self):
        ''' Use the direction in gesture file name to get correct button label

        Extract scroll direction, e.g., 'up' or 'down', from the gesture file
        name. Use the scroll direction to derive the correct button label.
        E.g., for direction = 'up':
              'Button Wheel' in config file is replaced by 'Button Wheel Up'
        '''
        direction = self._get_direction()
        button_label = self.xbutton.wheel_label_dict[direction]
        return button_label

    def _get_button_crit_per_direction(self):
        ''' Use the direction in gesture file name to get correct button label
            in button criteria
        '''
        button_crit = list(self.criteria['button'])
        button_crit[0] = self._get_button_wheel_label_per_direction()
        return button_crit

    ''' _verify_xxx()
    Generic verification methods for various functionalities / areas
    '''

    def _verify_motion(self, crit_tot_movement):
        ''' Verify if the observed motions satisfy the criteria '''
        op, val = self._motion_criteria(crit_tot_movement)
        self.motion_flag = op(self.xevent.sum_move, val)
        logging.info('        Verify motion: (%s)' %
                     Xcheck.RESULT_STR[self.motion_flag])
        logging.info('              Total movement = %d' % self.xevent.sum_move)

    def _verify_button(self, crit_button):
        ''' Verify if the observed buttons satisfy the criteria

        Example of computing count_flag:
            compare =              (  eq,  ge,    eq, ...)
            xevent.count_buttons = (   0,   3,     0, ...)
            crit_count =           (   0,   1,     0, ...)
            result list =          [True, True, True, ...]
            count_flag =           True   (which is the AND of the result_list)
        '''

        if crit_button is not None and crit_button[0] == 'Button Wheel':
            crit_button = self._get_button_crit_per_direction()
        op, crit_count = self._button_criteria(crit_button)
        compare = self._compare(tuple(op))

        # Compare if all parsed button counts meet the criteria
        count_flag = compare(self.xevent.count_buttons, crit_count)

        # An X Button must end with a ButtonRelease
        state_flags = map(lambda s: s == 'ButtonRelease',
                          self.xevent.button_states)
        state_flag = reduce(and_, state_flags)

        self.button_flag = state_flag and count_flag

        logging.info('        Verify button: (%s)' %
                     Xcheck.RESULT_STR[self.button_flag])
        button_msg_details = '              %s %d times'
        count_flag = False
        for idx, b in enumerate(self.button_labels):
            if self.xevent.count_buttons[idx] > 0:
                logging.info(button_msg_details %
                             (b, self.xevent.count_buttons[idx]))
                count_flag = True
        if not count_flag:
            logging.info('              No Button events detected.')


    def _verify_select_delay(self, crit_delay):
        ''' Verify if the delay time satisfy the criteria

        The delay time is defined to be the time interval between the time
        the 2nd finger touching the trackpad and the time of the corresponding
        X Motion event.
        '''
        # Extract scroll direction, i.e., 'up' or 'down', from the file name
        # We do not support scrolling 'left' or 'right' at this time.
        pos = self.func_name_pos
        direction = self._get_direction()

        # Derive the device event playback time when the 2nd finger touches
        dev_event_time = self.dev.get_2nd_finger_touch_time(direction)

        # Derive the motion event time of the 2nd finger
        found_ButtonPress = False
        event_time = None
        for line in self.xevent.xevent_data:
            event_name = line[0]
            event_dict = line[1]
            if not found_ButtonPress and event_name == 'ButtonPress':
                found_ButtonPress = True
            elif found_ButtonPress and event_name == 'MotionNotify':
                event_time = float(event_dict['time'])
                break

        if dev_event_time is None or event_time is None:
            delay = 'Not found'
            self.delay_flag = False
        else:
            delay = (event_time - dev_event_time) * 0.001
            self.delay_flag = delay < crit_delay
        logging.info('        Verify delay: (%s)' %
                     Xcheck.RESULT_STR[self.delay_flag])
        logging.info('              Delay time = %s (criteria = %f)' %
                     (str(delay), crit_delay))

    def _verify_wheel_speed(self, crit_wheel_speed):
        ''' Verify if the observed button wheel speed satisfies the criteria

        xevent_seq for two-finger scrolling looks like:
            ('Motion', (0, ('Motion_x', 0), ('Motion_y', 0)))
            ('NOP', 'Two Finger Touch')
            ('Button Wheel Down', 62)
            ('Button Horiz Wheel Right', 1)
            ('Button Wheel Down', 65)
            ('Button Horiz Wheel Right', 1)
            ('Button Wheel Down', 32)
            ('Button Horiz Wheel Right', 1)
            ('Button Wheel Down', 35)
            ('Button Horiz Wheel Right', 2)
            ('Button Wheel Down', 15)
            ('NOP', 'Two Finger Touch')
            ('Button Wheel Down', 185)
            ('NOP', 'Two Finger Touch')
            ('Motion', (22.0, ('Motion_x', 11), ('Motion_y', 19)))
            ('Button Wheel Down', 68)
            ('Motion', (0, ('Motion_x', 0), ('Motion_y', 0)))

        Need to accumulate the button counts partitioned by NOP (two finger
        touching event). The Button Wheel event count derived in this way
        should satisfy the wheel speed criteria.
        '''

        # Aggregate button counts partitioned by 'NOP'
        button_count_list = []
        init_time = [None, None]
        rounds = 0
        for line in self.xevent.xevent_seq:
            event_name, event_count, event_time = line
            if event_name == 'NOP':
                button_count = self.xbutton.init_button_struct_with_time(0,
                               init_time)
                button_count_list.append(button_count)
                rounds += 1
            elif rounds > 0:
                if event_name.startswith('Button'):
                    button_value = self.xbutton.get_value(event_name)
                    count = button_count_list[rounds-1][button_value][0]
                    if count == 0:
                        button_count_list[rounds-1][button_value][1] = \
                                event_time
                    else:
                        button_count_list[rounds-1][button_value][1][1] = \
                                event_time[1]
                    # TODO(josephsih): It is hard to follow this code; It would
                    # be better if this used an associative array ['event']
                    # ['count'], dictionary or class instead of just [0] and
                    # [1].
                    button_count_list[rounds-1][button_value][0] += event_count

        speed =[0] * rounds
        # Calculate button wheel speed
        for i, button_count in enumerate(button_count_list):
            speed[i] = self.xbutton.init_button_struct(0)
            for k, v in button_count.iteritems():
                if v[0] > 0:
                    time_list = button_count[k][1]
                    time_interval = (time_list[1] - time_list[0]) / 1000.0
                    speed[i][k] = (button_count[k][0] / time_interval) \
                                  if time_interval != 0 else 1

        # Verify if the target button satisfies wheel speed criteria
        button_label = self._get_button_wheel_label_per_direction()
        self.wheel_speed_flag = True
        if rounds <= 1:
            self.wheel_speed_flag = False
        else:
            target_button_value = self.xbutton.get_value(button_label)
            comp_op = self.op_dict[crit_wheel_speed[1]]
            multiplier = crit_wheel_speed[2]
            for r in range(1, rounds):
                if not comp_op(speed[r][target_button_value],
                               speed[r-1][target_button_value] * multiplier):
                    self.wheel_speed_flag = False
                    break

        prefix_space0 = ' ' * 8
        prefix_space1 = ' ' * 10
        prefix_space2 = ' ' * 14
        msg_title = prefix_space0 + 'Verify wheel speed: (%s)'
        msg_round = prefix_space1 + 'Round %d of two-finger scroll:'
        msg_speed = '{0:<25s}: {1:7.2f} times/sec ({2:4} times in [{3} {4}])'
        msg_details = prefix_space2 + msg_speed
        logging.info(msg_title % Xcheck.RESULT_STR[self.wheel_speed_flag])
        for i, button_count in enumerate(button_count_list):
            logging.info(msg_round % i)
            for k, v in button_count.iteritems():
                if v[0] > 0:
                    logging.info(msg_details.format(self.xbutton.get_label(k),
                                 speed[i][k], v[0], str(v[1][0]), str(v[1][1])))

    def _verify_select_sequence(self, crit_sequence):
        ''' Verify event sequence against criteria sequence

        For example, the following event_sequence matches crit_sequence.
        event_sequence: [('ButtonPress', 'Button Left'),
                         ('Motion', 68),
                         ('ButtonRelease', 'Button Left')]
        crit_sequence:  (('ButtonPress', 'Button Left'),
                         ('Motion', '>=', 20),
                         ('ButtonRelease', 'Button Left'))
        '''
        op_le = self.op_dict['<=']
        axis_dict = {'left': 'x', 'right': 'x', 'up': 'y', 'down': 'y',
                     None: ''}
        self.seq_flag = True
        crit_move_ratio = self.criteria.get('move_ratio', 0)

        if '*' in crit_sequence:
            work_crit_sequence = list(crit_sequence)
            work_crit_sequence.reverse()
            work_xevent_seq = list(self.xevent.xevent_seq)
            work_xevent_seq.reverse()
        else:
            work_crit_sequence = crit_sequence
            work_xevent_seq = self.xevent.xevent_seq

        index = -1
        crit_e_type = None
        for e in work_xevent_seq:
            e_type = e[0]
            e_value = e[1]
            fail_msg = None
            if crit_e_type != '*':
                index += 1
            if index >= len(work_crit_sequence):
                fail_msg = 'Event (%s, %s) is extra compared to the criteria.'
                fail_para = (e_type, str(e_value))
                break
            crit_e = work_crit_sequence[index]
            crit_e_type = crit_e[0]

            if crit_e_type == 'Button Wheel':
                crit_e_type = self._get_button_wheel_label_per_direction()

            if crit_e_type == '*':
                pass
            elif e_type.startswith('Motion'):
                motion_val = e_value[0]
                motion_x_val = e_value[1][1]
                motion_y_val = e_value[2][1]
                if crit_e_type.startswith('Motion'):
                    crit_e_op = crit_e[1]
                    crit_e_val = crit_e[2]
                    op = self.op_dict[crit_e_op]
                    if crit_e_type == 'Motion':
                        crit_check = op(motion_val, crit_e_val)
                        if not crit_check:
                            fail_msg = '%s %s does not satisfy %s. '
                            fail_para = (crit_e_type, str(e_value), str(crit_e))
                            break
                    elif crit_e_type == 'Motion_x_or_y':
                        axis = axis_dict[self._get_direction()]
                        motion_axis_dict = {'x': {'this':  motion_x_val,
                                                  'other': motion_y_val},
                                            'y': {'this':  motion_y_val,
                                                  'other': motion_x_val}}
                        motion_axis_val = motion_axis_dict[axis]['this']
                        motion_other_val = motion_axis_dict[axis]['other']

                        check_this_axis = op(motion_axis_val, crit_e_val)
                        # If the criteria requests that one axis move more
                        # than a threshold value, the other axis should move
                        # much less. This is to confirm that the movement is
                        # in the right direction.
                        other_axis_cond = crit_e_op == '>=' or crit_e_op == '>'
                        bound_other_axis = motion_axis_val * crit_move_ratio
                        check_other_axis = (not other_axis_cond or
                                    op_le(motion_other_val, bound_other_axis))
                        crit_check = check_this_axis and check_other_axis
                        if not crit_check:
                            fail_msg = '%s %s does not satisfy %s. ' \
                                       'Check motion for this axis = %s. ' \
                                       'Check motion for the other axis = %s'
                            fail_para = (crit_e_type, str(e_value), str(crit_e),
                                         check_this_axis, check_other_axis)
                            break
                    else:
                        fail_msg = '%s does not conform to the format.'
                        fail_para = crit_e_type
                        break
                else:
                    # No motion allowed
                    if e_value > 0:
                        fail_msg = 'Motion %d is not allowed.'
                        fail_para = e_value
                        break
            elif e_type == crit_e_type == 'ButtonPress' or \
                 e_type == crit_e_type == 'ButtonRelease':
                # Check if the button label matches criteria
                if e_value != crit_e[1]:
                    fail_msg = 'Button %s does not match %s.'
                    fail_para = (e_value, crit_e[1])
                    break
            elif e_type == crit_e_type == 'NOP':
                pass
            elif e_type.startswith('Button Wheel') and e_type == crit_e_type:
                op_str = crit_e[1]
                comp_op = self.op_dict[op_str]
                crit_button_count = crit_e[2]
                if not comp_op(e_value, crit_button_count):
                    fail_msg = '%s count %d does not satisfy "%s" %d.'
                    fail_para = (e_type, e_value, op_str, crit_button_count)
                    break
            else:
                fail_msg = 'Event %s does not match criteria %s.'
                fail_para = (e_type, crit_e_type)
                break

        # Check if the criteria has been fully matched
        if fail_msg is None and index < len(crit_sequence) - 1:
            fail_msg = 'Some events are missing compared to the criteria: %s.'
            fail_para = str(crit_sequence)

        if fail_msg is not None:
            self.seq_flag = False

        logging.info('        Verify select sequence: (%s)' %
                     Xcheck.RESULT_STR[self.seq_flag])
        logging.info('              Detected event sequence')
        for e in self.xevent.xevent_seq:
            logging.info('                      ' + str(e))
        if not self.seq_flag:
            logging.info('              ' + fail_msg % fail_para)

    def _verify_all_criteria(self):
        ''' A general verification method for all criteria

        This is the core method invoked for every functionality. What to check
        is based on the criteria specified for the functionality in the
        config file.
        '''
        # A dictionary mapping criterion to its verification method
        criteria_method = {'total_movement': self._verify_motion,
                           'button': self._verify_button,
                           'delay': self._verify_select_delay,
                           'wheel_speed': self._verify_wheel_speed,
                           'sequence': self._verify_select_sequence,
         }

        # Insert NOP based on criteria
        self._insert_nop_per_criteria(criteria_method)

        # Parse X button and motion events and aggregate the results.
        self.xevent.parse_button_and_motion()

        # Check those criteria specified in the config file.
        for c in criteria_method:
            if self.criteria.has_key(c):
                crit_item = self.criteria[c]
                criteria_method[c](crit_item)

        # AND all results of various criteria.
        self._get_result()

    def run(self, tp_func, tp_data,  xevent_str):
        ''' Parse the x events and invoke a proper check function

        Invoke the corresponding check function based on its functionality name.
        For example, tp_func.name == 'no_cursor_wobble' will result in the
        invocation of self._check_no_cursor_wobble()
        '''
        parse_result = self.xevent.parse_raw_string(xevent_str)
        self.gesture_file_name = tp_data.file_basename
        self.func_name_pos = 0 if tp_data.prefix is None else 1
        self.criteria = tp_func.criteria
        if parse_result:
            self._set_flags()
            self._verify_all_criteria()
            return self.result
        else:
            return False
