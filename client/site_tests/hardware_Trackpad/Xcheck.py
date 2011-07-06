# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

''' A module verifying whether X events satisfy specified criteria '''

import logging
import os
import re
import time
import utils

import trackpad_device
import trackpad_util

from operator import le, ge, eq, lt, gt, ne, and_


class XButton:
    ''' Manipulation of X Button labels and values '''

    # Define some common X button values
    Left = 1
    Middle = 2
    Right = 3
    Wheel_Up = 4
    Wheel_Down = 5
    Wheel_Left = 6
    Wheel_Right = 7
    Mouse_Wheel_Up = 8
    Mouse_Wheel_Down = 9

    def __init__(self):
        self.display_environ = trackpad_util.Display().get_environ()
        self.xinput_list_cmd = ' '.join([self.display_environ, 'xinput --list'])
        self.xinput_dev_cmd = ' '.join([self.display_environ,
                                        'xinput --list --long %s'])
        self.trackpad_dev_id = self._get_trackpad_dev_id()

    def _get_trackpad_dev_id(self):
        trackpad_dev_id = None
        if os.system('which xinput') == 0:
            input_dev_str = utils.system_output(self.xinput_list_cmd)
            for dev_str in input_dev_str.splitlines():
                res = re.search(r'(t(ouch|rack)pad\s+id=)(\d+)', dev_str, re.I)
                if res is not None:
                    trackpad_dev_id = res.group(3)
                    break
        return trackpad_dev_id

    def get_supported_buttons(self):
        ''' Get supported button labels from xinput

        a device returned from 'xinput --list' looks like:
        |   SynPS/2 Synaptics TouchPad       id=11   [slave  pointer (2)]

        Button labels returned from 'xinput --list <device_id>' looks like:
        Button labels: Button Left Button Middle Button Right Button Wheel Up
        Button Wheel Down Button Horiz Wheel Left Button Horiz Wheel Right
        Button 0 Button 1 Button 2 Button 3 Button 4 Button 5 Button 6
        Button 7
        '''
        DEFAULT_BUTTON_LABELS = (
                'Button Left', 'Button Middle', 'Button Right',
                'Button Wheel Up', 'Button Wheel Down',
                'Button Horiz Wheel Left', 'Button Horiz Wheel Right',
                'Button 0', 'Button 1', 'Button 2', 'Button 3',
                'Button 4', 'Button 5', 'Button 6', 'Button 7')

        if self.trackpad_dev_id is not None:
            features = utils.system_output(self.xinput_dev_cmd %
                                           self.trackpad_dev_id)
            button_labels_str = [line for line in features.splitlines()
                                 if line.lstrip().startswith('Button labels:')]
            strip_str = button_labels_str[0].lstrip().lstrip('Button labels:')
            self.button_labels = tuple(['Button ' + b.strip() for b in
                                        strip_str.split('Button')
                                        if len(b) > 0])
        else:
            logging.warn('Cannot find trackpad device in xinput. '
                         'Using default Button Labels instead.')
            self.button_labels = DEFAULT_BUTTON_LABELS
        logging.info('Button Labels (%d) in the trackpad: %s' %
                     (len(self.button_labels), self.button_labels))

        return self.button_labels

    def get_value(self, button_label):
        ''' Mapping an X button label to an X button value

        For example, 'Button Left' returns 1
                     'Button Wheel Up' returns 4
                     'Button Wheel Down' returns 5
        '''
        return self.button_labels.index(button_label) + 1

    def get_label(self, button_value):
        ''' Mapping an X button value to an X button label

        For example, 1 returns 'Button Left'
                     4 returns 'Button Wheel Up'
                     5 returns 'Button Wheel Down'
        '''
        return self.button_labels[button_value - 1]

    def get_index(self, button_label):
        ''' Mapping an X button label to its index in a button tuple

        Generally, a button index is equal to its button value decreased by 1.
        For example, 'Button Left' returns 0
                     'Button Wheel Up' returns 3
                     'Button Wheel Down' returns 4
        '''
        return self.button_labels.index(button_label)

    def init_button_struct(self, value):
        ''' Initialize a button dictionary to the given values. '''
        return dict(map(lambda b: (self.get_value(b), value),
                                  self.button_labels))


class Xcheck:
    ''' Check whether X events observe test criteria '''
    RESULT_STR = {True : 'Pass', False : 'Fail'}

    def __init__(self, dev):
        self.dev = dev
        self.xevent_data = None
        self.xbutton = XButton()
        self.button_labels = self.xbutton.get_supported_buttons()
        # Create a dictionary to look up button label
        #        e.g., {1: 'Button Left', ...}
        self.button_dict = dict(map(lambda b:
                                    (self.xbutton.get_value(b), b),
                                    self.button_labels))
        self._get_boot_time()

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

    def _calc_distance(self, x0, y0, x1, y1):
        ''' A simple Manhattan distance '''
        return abs(x1 - x0) + abs(y1 - y0)

    def _parse_button_and_motion(self):
        ''' Parse button events and motion events

        The variable seg_move accumulates the motions of the contiguous events
        segmented by some boundary events such as Button events and other
        NOP events. A NOP (no operation) event is a fake X event which is
        used to indicate the occurrence of some related device events.
        '''
        self.count_buttons = self.xbutton.init_button_struct(0)
        self.count_buttons_press = self.xbutton.init_button_struct(0)
        self.count_buttons_release = self.xbutton.init_button_struct(0)
        self.button_states = self.xbutton.init_button_struct('ButtonRelease')
        pre_x = pre_y = None
        self.event_seq = []
        seg_move = 0
        self.sum_move = 0

        indent1 = ' ' * 8
        indent2 = ' ' * 14
        log_msg = {True:  indent2 + '{0}   (button %d)',
                   False: indent2 + '{0} mis-matched  (button %d)'}
        precede_state = {'ButtonPress': 'ButtonRelease',
                         'ButtonRelease': 'ButtonPress',}
        logging.info(indent1 + 'X button events detected:')

        for line in self.xevent_data:
            event_name = line[0]
            if event_name != 'NOP':
                event_dict = line[1]
                if event_dict.has_key('coord'):
                    event_coord = eval(event_dict['coord'])
                if event_dict.has_key('button'):
                    event_button = eval(event_dict['button'])

            if event_name == 'EnterNotify':
                if (pre_x, pre_y) == (None, None):
                    pre_x, pre_y = event_coord
            elif event_name == 'MotionNotify':
                if (pre_x, pre_y) == (None, None):
                    pre_x, pre_y = event_coord
                else:
                    cur_x, cur_y = event_coord
                    move = self._calc_distance(pre_x, pre_y, cur_x, cur_y)
                    pre_x, pre_y = cur_x, cur_y
                    seg_move += move
                    self.sum_move += move
            elif event_name.startswith('Button'):
                self.event_seq.append(('Motion', seg_move))
                seg_move = 0
                button_label = self.xbutton.get_label(event_button)
                self.event_seq.append((event_name, button_label))
                prev_button_state = self.button_states[event_button]
                self.button_states[event_button] = event_name
                # A ButtonRelease should precede ButtonPress
                # A ButtonPress should precede ButtonRelease
                precede_flag = prev_button_state == precede_state[event_name]
                if event_name == 'ButtonPress':
                    self.count_buttons_press[event_button] += 1
                elif event_name == 'ButtonRelease':
                    self.count_buttons_release[event_button] += 1
                    self.count_buttons[event_button] += precede_flag
                logging.info(log_msg[precede_flag].format(event_name) %
                             event_button)
            elif event_name == 'NOP':
                self.event_seq.append(('Motion', seg_move))
                self.event_seq.append(('NOP', line[1]))
                seg_move = 0

        self.event_seq.append(('Motion', seg_move))

        # Convert dictionary to tuple
        self.button_states = tuple(self.button_states.values())
        self.count_buttons= tuple(self.count_buttons.values())

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

    def _get_button_criteria(self, button):
        ''' Convert the key of the button tuple from label to index '''
        crit_button_count = [0,] * len(self.button_labels)
        if button is not None:
            button_label, button_value = button
            button_index = self.xbutton.get_index(button_label)
            crit_button_count[button_index] = button_value
        return tuple(crit_button_count)

    def _insert_nop(self, nop_str):
        ''' Insert a 'NOP' fake event into the xevent_data

        NOP is not an X event. It is inserted to indicate the occurrence of
        related device events.
        '''
        lifted_time = self.dev.get_2nd_finger_lifted_time()
        if lifted_time is None:
            logging.warn('Cannot get time for %s.' % nop_str)
        else:
            for index, line in enumerate(self.xevent_data):
                event_name = line[0]
                event_dict = line[1]
                if event_name == 'MotionNotify':
                    event_time = float(event_dict['time'])
                    if event_time > lifted_time:
                        self.xevent_data.insert(index, ('NOP', nop_str))
                        break

    ''' _verify_xxx()
    Generic verification methods for various functionalities / areas
    '''

    def _verify_motion(self, compare, crit_max_movement):
        ''' Verify if the observed motions satisfy the criteria '''
        self.motion_flag = compare(self.sum_move, crit_max_movement)
        logging.info('        Verify motion: (%s)' %
                     Xcheck.RESULT_STR[self.motion_flag])
        logging.info('              Total movement = %d' % self.sum_move)

    def _verify_button(self, compare, crit_button_count):
        ''' Verify if the observed buttons satisfy the criteria '''
        count_flag = compare(self.count_buttons, crit_button_count)
        state_flags = map(lambda s: s == 'ButtonRelease', self.button_states)
        state_flag = reduce(and_, state_flags)
        self.button_flag = state_flag and count_flag

        logging.info('        Verify button: (%s)' %
                     Xcheck.RESULT_STR[self.button_flag])
        button_msg_details = '              %s %d times'
        count_flag = False
        for idx, b in enumerate(self.button_labels):
            if self.count_buttons[idx] > 0:
                logging.info(button_msg_details % (b, self.count_buttons[idx]))
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
        direction = self.gesture_file_name.split('-')[pos].split('.')[-1]

        # Derive the device event playback time when the 2nd finger touches
        dev_event_time = self.dev.get_2nd_finger_touch_time(direction)

        # Derive the motion event time of the 2nd finger
        found_ButtonPress = False
        event_time = None
        for line in self.xevent_data:
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
        op = {'>=': ge, '<=': le, '==': eq, '=': eq, '>': gt, '<': lt,
              '!=': ne, '~=': ne, 'not': ne, 'is not': ne}
        self.seq_flag = True
        index = -1
        for e in self.event_seq:
            e_type, e_value = e
            fail_msg = None
            index += 1
            if index >= len(crit_sequence):
                fail_msg = 'Event (%s, %s) is extra compared to the criteria.'
                fail_para = (e_type, str(e_value))
                break
            crit_e = crit_sequence[index]
            crit_e_type = crit_e[0]

            if e_type == 'Motion':
                if crit_e_type == 'Motion':
                    # Check if the motion matches the criteria
                    if not op[crit_e[1]](e_value, crit_e[2]):
                        fail_msg = 'Motion %d does not satisfy %s'
                        fail_para = (e_value, str(crit_e))
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
        for e in self.event_seq:
            logging.info('                      ' + str(e))
        if not self.seq_flag:
            logging.info('              ' + fail_msg % fail_para)

    ''' _verify_area_xxx()
    The following methods are generally used for the group of functionalities
    in the same area.
    '''

    def _verify_area_click(self):
        ''' A general verification method for the area: 1 finger point & click

        This function is invoked for several functionalities in the same area.
        Criteria:
        1. The sum of movement is less than or equal to crit_max_movement
        2. The number of clicks is as specified.
        '''
        crit_max_movement = self.criteria['max_movement']
        crit_button_count = self._get_button_criteria(self.criteria['button'])

        self._parse_button_and_motion()
        self._verify_motion(le, crit_max_movement)
        self._verify_button(eq, crit_button_count)
        self._get_result()

    def _verify_area_select(self):
        ''' A general verification method for the area: click & select/drag

        This function is invoked for several functionalities in the same area.
        Criteria:
        (1) The observed event sequnce should conform to the specified
            sequence in the criteria.
        (2) Optional: a delay time may be specified for the timing constraint
            between a device event and a corresponding X event.
        '''
        self._parse_button_and_motion()

        if self.criteria.has_key('movement'):
            self._verify_motion(ge, self.criteria['movement'])
        if self.criteria.has_key('button'):
            self._verify_button(eq, self._get_button_criteria(
                                                      self.criteria['button']))
        if self.criteria.has_key('delay'):
            self._verify_select_delay(self.criteria['delay'])
        if self.criteria.has_key('sequence'):
            self._verify_select_sequence(self.criteria['sequence'])
        self._get_result()

    ''' _check_xxx()
    For each functionality xxx, there is a corresponding _check_xxx() method
    which is executed by run() automatically.
    '''

    def _check_any_finger_click(self):
        ''' Any finger, including thumb, can click '''
        self._verify_area_click()

    def _check_any_angle_click(self):
        ''' Finger can be oriented at any angle relative to trackpad '''
        self._verify_area_click()

    def _check_any_location_click(self):
        ''' Click can occur at any location on trackpad (no hot zones) '''
        self._verify_area_click()

    def _check_no_min_width_click(self):
        ''' First finger should not have any minimum width defined for it
        (i.e., point and/or click with finger tip. E.g., click with fingernail)
        '''
        self._verify_area_click()

    def _check_no_cursor_wobble(self):
        ''' No cursor wobble, creep, or jumping (or jump back) during clicking
        '''
        self._verify_area_click()

    def _check_drum_roll(self):
        ''' Drum roll: One finger (including thumb) touches trackpad followed
        shortly (<500ms) by a second finger touching trackpad should not result
        in cursor jumping
        '''
        self._verify_area_click()

    def _check_single_finger_select(self):
        ''' (Single finger) Finger physical click or tap & a half, then finger -
        remaining in contact with trackpad - drags along surface of trackpad
        '''
        self._verify_area_select()

    def _check_single_finger_lifted(self):
        ''' (Single finger) If finger leaves trackpad for only 800ms-1s
        (Synaptics UX should know value), select/drag should continue
        '''
        self._verify_area_select()

    def _check_two_fingers_select(self):
        ''' (Two fingers) 1st finger click or tap & a half, 2nd finger's
        movement selects/drags
        '''
        self._verify_area_select()

    def _check_two_fingers_lifted(self):
        ''' (Two fingers) Continues to drag when second finger is lifted then
        placed again
        '''
        self._insert_nop('2nd Finger Lifted')
        self._verify_area_select()

    def _check_two_fingers_no_delay(self):
        ''' (Two fingers) Drag should be immediate (no delay between movement
        of finger and movement of selection/drag)
        '''
        self._verify_area_select()

    def _check_two_finger_scroll(self):
        ''' Vertical scroll, reflecting movement of finger(s)

        Criteria:
        1. sum of movement is less than crit_max_movement
        2. if subname in the file name is up:
               A number of button 4 (Wheel Up) events should be observed
               without other button events.
           elif subname in the file name is down:
               A number of button 5 (Wheel Down) events should be observed
               without other button events.
        '''
        # Extract scroll direction, i.e., 'up' or 'down', from the file name
        pos = self.func_name_pos
        direction = self.gesture_file_name.split('-')[pos].split('.')[1]

        # Get criteria for max movement and wheel up/down
        crit_max_movement = self.criteria['max_movement']
        ops = [eq,] * len(self.button_labels)
        if direction == 'up':
            button_label = self.xbutton.get_label(self.xbutton.Wheel_Up)
            ops[self.xbutton.get_index(button_label)] = ge
            crit_up = self.criteria['button'][0]
            crit_button_count = self._get_button_criteria(crit_up)
        elif direction == 'down':
            button_label = self.xbutton.get_label(self.xbutton.Wheel_Down)
            ops[self.xbutton.get_index(button_label)] = ge
            crit_down = self.criteria['button'][1]
            crit_button_count = self._get_button_criteria(crit_down)
        else:
            msg = '      scroll direction in the file name is not correct: (%s)'
            logging.info(msg % direction)
            self.result = False
            return

        self._parse_button_and_motion()
        self._verify_motion(le, crit_max_movement)
        self._verify_button(self._compare(tuple(ops)), crit_button_count)
        self._get_result()

    def _extract_prop(self, event_name, line, prop_key):
        ''' Extract property from X events '''
        if line is None:
            logging.warn('      X event format may not be correct.')
            return None

        # Declare the format to extract information from X event structures
        format_dict = {
            'Motion_coord'  : '{6}',
            'Motion_time'   : '{5}',
            'Motion_tv'     : '{7}',
            'Button_coord'  : '{6}',
            'Button_button' : '{3}',
            'Button_time'   : '{5}',
            'Button_tv'     : '{7}',
        }
        event_format_str = format_dict[event_name]

        try:
            prop_val = event_format_str.format(*line.strip().split()).strip(',')
        except IndexError, err:
            logging.warn('      %s in X event data.' % str(err))
            return None
        return (prop_key, prop_val)

    def _parse(self, xevent_str):
        ''' Parse all X events

        The event information of a single X event may span across multiple
        lines. This function extracts the important event information of
        an event into a dictionary so that it is easier to process in
        subsequent stages.

        For example:
        A MotionNotify event looks like:
            MotionNotify event, serial 25, synthetic NO, window 0xa00001,
                root 0xab, subw 0x0, time 925196, (750,395), root:(750,395),
                state 0x0, is_hint 0, same_screen YES

        A ButtonPress event looks like:
            ButtonPress event, serial 25, synthetic NO, window 0xa00001,
                root 0xab, subw 0x0, time 1098904, (770,422), root:(770,422),
                state 0x0, button 1, same_screen YES

        The property extracted for the MotionNotify event looks like:
            ['MotionNotify', {'coord': (150,200), 'time': ...]

        The property extracted for the ButtonPress event looks like:
            ['ButtonPress', {'coord': (150,200), 'button': 5}, 'time': ...]
        '''

        if len(xevent_str) == 0:
            logging.warn('    No X events were captured.')
            return False

        xevent_iter = iter(xevent_str)
        self.xevent_data = []
        while True:
            line = next(xevent_iter, None)
            if line is None:
                break
            line_words = line.split()
            if len(line_words) > 0:
                event_name = line_words[0]
            else:
                continue

            # Extract event information for important event types
            if event_name == 'MotionNotify' or event_name == 'EnterNotify':
                line1 = next(xevent_iter, None)
                line2 = next(xevent_iter, None)
                prop_coord = self._extract_prop('Motion_coord', line1, 'coord')
                prop_time = self._extract_prop('Motion_time', line1, 'time')
                if prop_coord is not None and prop_time is not None:
                    event_dict = dict([prop_coord, prop_time])
                    self.xevent_data.append([event_name, event_dict])
            elif line.startswith('Button'):
                line1 = next(xevent_iter, None)
                line2 = next(xevent_iter, None)
                prop_coord = self._extract_prop('Button_coord', line1, 'coord')
                prop_time = self._extract_prop('Button_time', line1, 'time')
                prop_button = self._extract_prop('Button_button', line2,
                                                 'button')
                if (prop_coord is not None and prop_button is not None
                                           and prop_time is not None):
                    event_dict = dict([prop_coord, prop_button, prop_time])
                    self.xevent_data.append([event_name, event_dict])
        return True

    def run(self, tp_func, tp_data,  xevent_str):
        ''' Parse the x events and invoke a proper check function

        Invoke the corresponding check function based on its functionality name.
        For example, tp_func.name == 'no_cursor_wobble' will result in the
        invocation of self._check_no_cursor_wobble()
        '''
        parse_result = self._parse(xevent_str)
        self.gesture_file_name = tp_data.file_basename
        self.func_name_pos = 0 if tp_data.prefix is None else 1
        self.criteria = tp_func.criteria
        if parse_result:
            check_function = eval('self._check_' + tp_func.name)
            self._set_flags()
            check_function()
            return self.result
        else:
            return False
