# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

''' A module verifying whether X events satisfy specified criteria '''

import copy
import logging

import common_util
import constants
import trackpad_util
import Xevent

from operator import le, ge, eq, lt, gt, ne, and_
from trackpad_util import read_trackpad_test_conf, debug


# Declare NOP as a instance containing NOP related constants
NOP = constants.NOP()


class Xcheck:
    ''' Check whether X events observe test criteria '''
    RESULT_STR = {True: 'Pass', False: 'Fail'}

    def __init__(self, dev, conf_path):
        self.dev = dev
        self.conf_path = conf_path
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
        self.motion_list = ['Motion', 'Motion_x', 'Motion_y']

    def _get_boot_time(self):
        ''' Get the system boot up time

        Boot time can be used to convert the elapsed time since booting up
        to that since Epoch.
        '''
        stat_cmd = 'cat /proc/stat'
        stat = common_util.simple_system_output(stat_cmd)
        boot_time_tuple = tuple(int(line.split()[1])
                                for line in stat.splitlines()
                                if line.startswith('btime'))
        if not boot_time_tuple:
            raise error.TestError('Fail to extract boot time by "%s"' %
                                  stat_cmd)
        self.boot_time = boot_time_tuple[0]

    def _set_result_flags(self):
        ''' Set all result flags to True before invoking check function '''
        self.motion_flag = True
        self.button_flag = True
        self.button_dev_flag = True
        self.delay_flag = True
        self.wheel_speed_flag = True
        self.seq_flag = True
        self.button_seg_flag = True
        self.result_flags = ('self.motion_flag',
                             'self.button_flag',
                             'self.button_dev_flag',
                             'self.delay_flag',
                             'self.wheel_speed_flag',
                             'self.seq_flag',
                             'self.button_seg_flag')

    def _get_result(self):
        ''' Get the final result from various check flags '''
        # Evaluate the result_flags
        flags = map(eval, self.result_flags)
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

    def _button_criteria(self, button_labels, button_crit):
        ''' Create a list of button criteria
        This supports a list of button_labels in a more flexible way.

        For example,
        button_labels: ('Button Horiz Wheel Left', 'Button Horiz Wheel Right')
        button_crit: ('Button Wheel', '>=', 10)

        And assume that button_labels = (
            'Button Left', 'Button Middle', 'Button Right',
            'Button Wheel Up', 'Button Wheel Down',
            'Button Horiz Wheel Left', 'Button Horiz Wheel Right', ...)

        The result of this method is
        ops =    (eq, eq, eq, eq, eq, ge, ge, ...)
        values = ( 0,  0,  0,  0,  0, 10, 10, ...)
        '''
        len_button_labels = len(self.button_labels)
        ops = [eq] * len_button_labels
        values = [0] * len_button_labels
        if button_crit is not None:
            for button_label in button_labels:
                _, button_op, button_value = button_crit
                button_index = self.xbutton.get_index(button_label)
                ops[button_index] = self.op_dict[button_op]
                values[button_index] = button_value
        return (ops, values)

    def _insert_fake_event(self, criterion, fake_xevent_value,
                           fake_xevent_name=NOP.NOP):
        ''' Insert a fake X event into the xevent_data

        A NOP event is not an X event. It is inserted to indicate the
        occurrence of related device events.
        '''
        if fake_xevent_value == NOP.TWO_FINGER_TOUCH:
            dev_event_time = self.dev.get_two_finger_touch_time_list()
        elif (criterion == 'button_dev'):
            dev_event_time = self.dev.find_all_event_time(fake_xevent_value)
        else:
            dev_event_time = self.dev.get_finger_time(fake_xevent_value)

        if not dev_event_time:
            logging.warning('Fail to get time for "%s" in device file.' %
                         fake_xevent_value)
            return

        # Insert fake_xevent_name event into xevent data
        begin_index = 0
        for devent_time in dev_event_time:
            found_insert_index = False
            fake_event = [fake_xevent_name, {'event': fake_xevent_value,
                                             'time': devent_time}]
            for index, line in enumerate(self.xevent.xevent_data[begin_index:]):
                xevent_dict = line[1]
                xevent_time = float(xevent_dict.get('time', 0))
                if xevent_time > devent_time:
                    insert_index = begin_index + index
                    self.xevent.xevent_data.insert(insert_index, fake_event)
                    begin_index = insert_index + 1
                    found_insert_index = True
                    break
            if not found_insert_index:
                self.xevent.xevent_data.append(fake_event)

    def _insert_nop_per_criteria(self, criteria_method):
        ''' Insert NOP events based on criteria '''
        for c in criteria_method:
            crit = self._match_criteria_with_subname(c)
            if crit is not None:
                if c == 'wheel_speed':
                    # There are a couple of times of two-finger scrolling.
                    # Insert NOP between them in self.xevent_seq
                    self._insert_fake_event(c, NOP.TWO_FINGER_TOUCH)
                elif c in ['sequence', 'button_segment', 'button_dev']:
                    crit_item = self.criteria[crit]
                    # crit_item could be either 'sequence' or 'button_segment'
                    #
                    # 'sequence'
                    # Insert NOP in self.xevent_seq if NOP is specified
                    # in sequence criteria.
                    # Example of criteria of 'sequence' below:
                    #   ('NOP', '1st Finger Lifted')
                    #   ('NOP', '2nd Finger Lifted')
                    #
                    # 'button_segment'
                    # Insert NOP (device) event into self.xevent_seq if
                    # 'NOP' is specified in button_segment criteria.
                    # Example of criteria of 'button_segment' below:
                    #   ('NOP', ('Device Mouse Click Press', 'before', True))
                    #   ('NOP', ('Device Mouse Click Release', 'between', True))
                    #
                    # 'button_dev'
                    # Insert NOP (device) event into self.xevent_seq if
                    # 'NOP' is specified in button criteria.
                    # Example of criteria of 'button_segment' below:
                    #   ('NOP', ('Finger On', None))
                    #   ('NOP', ('Device Mouse Click Release', True))
                    #   ('NOP', ('Finger Off', None))
                    #
                    for s in crit_item:
                        if s[0] == NOP.NOP:
                            _, value = s
                            dev_ev = value if c == 'sequence' else value[0]
                            self._insert_fake_event(c, dev_ev)

    def _extract_func_name(self):
        ''' Extract functionality name plus subname from the gesture file name

        E.g., A file name looks like:
            palm-palm_presence.static.both-alex-jane-20111215_001214.dat
            Return value in this case: palm_presence.static.both
        '''
        return self.gesture_file_name.split('-')[self.func_name_pos]

    def _extract_subname(self):
        ''' Extract subname from the gesture file name

        E.g., A file name looks like:
            palm-palm_presence.static.both-alex-jane-20111215_001214.dat
            Return value in this case: static.both
        '''
        full_name = self._extract_func_name()
        name_seg = full_name.split('.', 1)
        return name_seg[1] if len(name_seg) > 1 else None

    def _get_direction(self):
        ''' Get a specific direction from functionality name '''
        directions = ['up', 'down', 'left', 'right']
        file_name = self._extract_func_name()
        for d in directions:
            if d in file_name:
                return d
        return None

    def _get_general_direction(self):
        ''' Get a general direction from functionality name '''
        direction = self._get_direction()
        if direction is not None:
            return direction
        directions = ['vert', 'horiz', 'alldir']
        file_name = self._extract_func_name()
        for d in directions:
            if d in file_name:
                return d
        return None

    def _get_more_directions(self):
        ''' Get direction(s) from functionality name '''
        dir_dict = {'vert': ('up', 'down'),
                    'horiz': ('left', 'right'),
                    'alldir': ('up', 'down', 'left', 'right')}
        direction = self._get_direction()
        if direction is not None:
            return (direction,)
        file_name = self._extract_func_name()
        for d in dir_dict.keys():
            if d in file_name:
                return dir_dict[d]

    def _get_button_wheel_label_per_direction(self):
        ''' Use the specific direction in gesture file name to get
        correct button label.

        Extract the scroll direction ('up', 'down', 'left', or 'right')
        from the gesture file name. Use the scroll direction to derive
        the correct button label.
        E.g., for direction = 'up':
              'Button Wheel' in config file is replaced by 'Button Wheel Up'
        '''
        direction = self._get_direction()
        button_label = self.xbutton.wheel_label_dict[direction]
        return button_label

    def _get_button_wheel_labels_from_directions(self):
        ''' Use the direction(s) in gesture file name to get the corresponding
        button wheel label(s)
        '''
        directions = self._get_more_directions()
        button_labels = [self.xbutton.wheel_label_dict[d] for d in directions]
        return button_labels

    def _match_criteria_with_subname(self, crit):
        ''' Determine if a given criterion crit could apply to a file with a
        particular subname

        E.g.,
        A file with subname of 'physical_click' could match the criteria:
            'button_segment'
            'button_segment(physical_click)'
        but not the criteria:
            'button_segment(tap_and_half)'
        '''
        subname = self._extract_subname()
        for c in self.criteria:
            if c == crit:
                return c
            elif subname is not None:
                crit_with_subname = '%s(%s)' % (crit, subname)
                if c == crit_with_subname:
                    return c

    ''' _verify_xxx()
    Generic verification methods for various functionalities / areas
    '''

    def _verify_motion(self, crit_tot_movement):
        ''' Verify if the observed motions satisfy the criteria '''
        op, val = self._motion_criteria(crit_tot_movement)
        self.motion_flag = op(self.xevent.sum_move, val)
        self.vlog.verify_motion_log(self.motion_flag, self.xevent.sum_move)

    def _verify_button(self, crit_button):
        ''' Verify if the observed buttons satisfy the criteria

        Example of computing count_flag:
            compare =              (  eq,  ge,    eq, ...)
            xevent.count_buttons = (   0,   3,     0, ...)
            crit_count =           (   0,   1,     0, ...)
            result list =          [True, True, True, ...]
            count_flag =           True   (which is the AND of the result_list)
        '''
        if crit_button is None:
            crit_button_labels = None
        elif crit_button[0] == 'Button Wheel':
            crit_button_labels = self._get_button_wheel_labels_from_directions()
        else:
            crit_button_labels = (crit_button[0],)

        op, crit_count = self._button_criteria(crit_button_labels, crit_button)
        compare = self._compare(tuple(op))

        # Compare if all parsed button counts meet the criteria
        count_flag = compare(self.xevent.count_buttons, crit_count)

        # An X Button must end with a ButtonRelease
        state_flags = map(lambda s: s == 'ButtonRelease',
                          self.xevent.button_states)
        state_flag = reduce(and_, state_flags)

        self.button_flag = state_flag and count_flag
        self.vlog.verify_button_log(self.button_flag, self.xevent.count_buttons)

    def _verify_button_with_device_events(self, crit_button_dev):
        ''' Verify if the observed button satisfy the criteria

        E.g., the critieria for
            'button_dev(physical_click)': (
                ('NOP', ('Finger On', None)),
                ('NOP', ('Device Mouse Click Press', True)),
                ('NOP', ('Device Mouse Click Release', True)),
                ('NOP', ('One Finger On', True)),
                ('Motion', '<=', 0),
                ('Button', 'Button Left'),
                ('NOP', ('Finger Off', None)),
            )

            The rules above make sure that
            (1) It only counts Button Left with a physical mouse click
            (2) Exactly one finger is observed.
            (3) Should match the number of physical mouse clicks.
            (4) Ignore finger tracking.

        Refer to configuration files (*.conf) for more details about the
        criteria.
        '''

        def _reset_button_dev_motion(self, button_dev_events):
            ''' Initialize button_dev motion events '''
            for m in self.motion_list:
                button_dev_events[m] = 0

        def _init_button_dev_events(self, motion_values=True):
            ''' Initialize button_dev_events '''
            button_dev_events = {}
            # Initialize 'NOP'
            button_dev_events['NOP'] = {}

            # Initialize 'Button'
            button_dev_events['Button'] = {}
            for b in self.button_labels:
                button_dev_events['Button'][b] = 0

            # Initialize 'Motion'
            if motion_values:
                for m in self.motion_list:
                    button_dev_events[m] = 0
            return button_dev_events

        def _check_button_dev_criteria(self, button_dev_events,
                                       crit_button_dev_events):
            ''' Check if the button_dev_events conform to the criteria '''
            fail_cause = []
            # Check all observed NOP device events match the corresponding
            # criteria
            crit_dup = copy.deepcopy(crit_button_dev_events)
            for e in button_dev_events['NOP']:
                # check if this NOP event is specified in the criteria
                if crit_button_dev_events['NOP'].has_key(e):
                    this_ev = button_dev_events['NOP'][e]
                    crit = crit_button_dev_events['NOP'][e]
                    crit_dup['NOP'].pop(e)
                    if this_ev == crit or crit == 'DONTCARE':
                        continue
                msg = 'NOP[%s]: %s' % (e, this_ev)
                fail_cause.append(msg)

            # Check if there are any NOP criteria not matched yet.
            if crit_dup['NOP']:
                for e in crit_dup['NOP']:
                    if (crit_dup['NOP'][e] != 'DONTCARE' and
                        crit_dup['NOP'][e]):
                        msg = ('NOP[%s]: %s is missing' %
                               (e, crit_dup['NOP'][e]))
                        fail_cause.append(msg)

            debug('    check Button: %s' % str(button_dev_events['Button']))
            debug('    check Button crit: %s' %
                  str(crit_button_dev_events['Button']))

            # Check Button event
            for b in self.button_labels:
                crit_button_count = crit_button_dev_events['Button'][b]
                button_count = button_dev_events['Button'][b]
                if button_count != crit_button_count:
                    msg = ('Count of Button[%s]: %d. It should be %d' %
                           (b, button_count, crit_button_count))
                    fail_cause.append(msg)

            # Check Motion events
            for m in self.motion_list:
                if crit_button_dev_events.has_key(m):
                    op_str, val = crit_button_dev_events[m]
                    op = self.op_dict[op_str]
                    if not op(button_dev_events[m], val):
                        msg = '%s: %s' % (m, button_dev_events[m])
                        fail_cause.append(msg)

            result = (len(fail_cause) == 0)
            return (result, fail_cause)

        def _parse_button_dev_criteria(self):
            ''' Parse the button_dev criteria '''
            crit_button_dev_events = _init_button_dev_events(self,
                                                      motion_values=False)

            for c in crit_button_dev:
                name = c[0]
                if name == 'NOP':
                    # E.g., ('NOP', ('Finger On', True)),
                    #       ('NOP', ('Device Mouse Click Release', True)),
                    name, (dev_event, value) = c
                    crit_button_dev_events[name][dev_event] = value
                elif name == 'Button':
                    # E.g., ('Button', 'Button Left')
                    # No need to specifiy the count in the criteria
                    # Will count it based on the gesture file.
                    name, button = c
                    self.button_dev_target = button
                    crit_button_dev_events[name][button] = 0
                elif name.startswith('Motion'):
                    # E.g., ('Motion', '<=', 0),
                    name, op, value = c
                    crit_button_dev_events[name] = (op, int(value))

            return crit_button_dev_events

        def _check_device_events(button_dev_events, crit_button_dev_events):
            ''' Check if all NOP device events except Finger On/Off
            are matched.

            If any NOP device event does not match, the user had made
            a wrong gesture. For example, a user may make tap-to-clicks
            when physical clicks are expected.
            '''
            flag_match = True
            debug('  button_dev_events: %s' % str(button_dev_events['NOP']))
            debug('  crit_button_dev_events: %s' %
                  str(crit_button_dev_events['NOP']))
            if len(crit_button_dev_events['NOP']) > 0:
                for ev in crit_button_dev_events['NOP']:
                    if not ev.startswith('Finger'):
                        if button_dev_events['NOP'].has_key(ev):
                            flag_match = (button_dev_events['NOP'][ev] ==
                                          crit_button_dev_events['NOP'][ev])
                        else:
                            flag_match = not crit_button_dev_events['NOP'][ev]
                        if not flag_match:
                            debug('  NOP[%s] violation' % ev)
                            break
            return flag_match

        def _init_file_accu_motion(self, file_accu_motion):
            for m in self.motion_list:
                file_accu_motion[m] = 0

        def _update_file_accu_motion(self, file_accu_motion, button_dev_events):
            for m in self.motion_list:
                file_accu_motion[m] += button_dev_events[m]

        def _check_button_dev(self, dev_event, button_dev_events,
                              crit_button_dev_events, file_accu_motion):
            # Check if there is a 'Finger On' event observed.
            if not button_dev_events['NOP'].has_key('Finger On'):
                msg = '  Warning: There is no Finger On before %s.' % dev_event
                logging.info(msg)
                return

            device_events_matched = _check_device_events(button_dev_events,
                                                         crit_button_dev_events)
            debug('  check device events: matched = %s' %
                  str(device_events_matched))
            if device_events_matched:
                result = _check_button_dev_criteria(self, button_dev_events,
                                                    crit_button_dev_events)
                debug('  *** result: %s' % str(result))
                result_flag, fail_cause = result
                self.fail_causes += fail_cause
                if self.button_dev_flag is None:
                    self.button_dev_flag = result_flag
                else:
                    self.button_dev_flag &= result_flag
                _update_file_accu_motion(self, file_accu_motion,
                                         button_dev_events)
            else:
                msg = '  check device events: not matched. Skip.'
                logging.info(msg)

        # Some initialization
        self.button_dev_flag = None
        self.fail_causes = []
        button_dev_events = _init_button_dev_events(self)
        state_button = {}
        for b in self.button_labels:
            state_button[b] = None
        state_click = None

        file_crit_button_count = 0
        file_button_count = 0
        file_accu_motion = {}
        _init_file_accu_motion(self, file_accu_motion)

        # Parse the criteria into a dictionary
        crit_button_dev_events = _parse_button_dev_criteria(self)
        target_button = self.button_dev_target

        # Match the xevent sequence against the criteria dictionary
        # For a normal Button Left resulting from a mouse click:
        #       (1) Finger On
        #       (2) One Finger On
        #       (3) Mouse Click Press
        #       (4) ButtonPress
        #       (5) Mouse Click Release
        #       (6) ButtonRelease
        #        .  (Optional: repeat Steps (3) ~ (6))
        #       (7) Finger Off
        xevent_seq = self.xevent.xevent_seq
        for ev in xevent_seq:
            name = ev[0]
            if name == 'ButtonPress':
                # E.g., ('ButtonPress', 'Button Left', 443854733)
                name, button, timestamp = ev
                if state_button[button] in ['ButtonRelease', None]:
                    state_button[button] = 'ButtonPress'
                    button_dev_events['Button'][button] += 0.5
                    debug('  %s(%s): state=%s count=%s '%
                          (name, button, state_button[button],
                           button_dev_events['Button'][button]))

            elif name == 'ButtonRelease':
                # E.g, ('ButtonRelease', 'Button Left', 443854884)
                name, button_released, timestamp = ev
                if state_button[button] == 'ButtonPress':
                    state_button[button] = 'ButtonRelease'
                    button_dev_events['Button'][button_released] += 0.5
                    debug('  %s(%s): state=%s count=%s '%
                          (name, button, state_button[button],
                           button_dev_events['Button'][button]))

            elif name == 'NOP':
                # E.g., ('NOP', 'Device Mouse Click Press')
                #       ('NOP', 'Device Mouse Click Release')
                name, dev_event, timestamp = ev
                button_dev_events[name][dev_event] = True

                # When finger off, check if all NOP device criteria are matched.
                if dev_event == 'Finger Off':
                    # Check button_dev criteria
                    _check_button_dev(self, dev_event, button_dev_events,
                                      crit_button_dev_events, file_accu_motion)
                    # Accumulate file-wise button counts
                    file_button_count += \
                            button_dev_events['Button'][target_button]
                    file_crit_button_count += \
                            crit_button_dev_events['Button'][target_button]
                    # Reset
                    button_dev_events = _init_button_dev_events(self)
                    crit_button_dev_events = _parse_button_dev_criteria(self)
                    _reset_button_dev_motion(self, button_dev_events)

                elif dev_event == 'Device Mouse Click Press':
                    # _reset_button_dev_motion(self, button_dev_events)
                    if state_click in ['Click Release', None]:
                        state_click = 'Click Press'
                        crit_button_dev_events['Button'][target_button] += 0.5
                        debug('  %s: target_button count = %s' % (dev_event,
                              crit_button_dev_events['Button'][target_button]))

                elif dev_event == 'Device Mouse Click Release':
                    if state_click == 'Click Press':
                        state_click = 'Click Release'
                        crit_button_dev_events['Button'][target_button] += 0.5
                        debug('  %s: target_button count = %s' % (dev_event,
                              crit_button_dev_events['Button'][target_button]))

            elif name == 'Motion':
                # E.g., ('Motion', (655.0, ('Motion_x', 605), ('Motion_y', 20)),
                #                  [443855715, 443858536])
                (name, (motion_val, (_, motion_x_val), (_, motion_y_val)),
                 timestamp) = ev
                button_dev_events['Motion'] += int(motion_val)
                button_dev_events['Motion_x'] += int(motion_x_val)
                button_dev_events['Motion_y'] += int(motion_y_val)

        debug('  *** vlog: button_dev_flag = %s' % self.button_dev_flag)
        self.vlog.verify_button_dev_log(self.button_dev_flag,
                                        xevent_seq,
                                        self.fail_causes,
                                        target_button,
                                        file_button_count,
                                        file_crit_button_count)

    def _verify_select_delay(self, crit_delay):
        ''' Verify if the delay time satisfy the criteria

        The delay time is defined to be the time interval between the time
        the 2nd finger touching the trackpad and the time of the corresponding
        X Motion event.
        '''
        # Extract scroll direction, i.e., 'up' or 'down', from the file name
        # We do not support scrolling 'left' or 'right' at this time.
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
            if event_name == NOP.NOP:
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

        speed = [0] * rounds
        # Calculate button wheel speed
        for i, button_count in enumerate(button_count_list):
            speed[i] = self.xbutton.init_button_struct(0)
            for k, v in button_count.iteritems():
                if v[0] > 0:
                    time_list = button_count[k][1]
                    time_interval = (time_list[1] - time_list[0]) / 1000.0
                    speed[i][k] = ((button_count[k][0] / time_interval)
                                   if time_interval != 0 else 1)

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
                                                    speed[i][k], v[0],
                                                    str(v[1][0]),
                                                    str(v[1][1])))

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

        def _get_criteria(index, crit_sequence):
            if index >= len(crit_sequence):
                crit_e = ''
                crit_e_type = ''
            else:
                crit_e = crit_sequence[index]
                crit_e_type = crit_e[0]
                # Add Button Wheel direction
                # Support only 'up', 'down', 'left', 'right' at this time in
                # sequence criteria.
                # May support 'vert', 'horiz', and 'alldir' later if needed.
                if crit_e_type == 'Button Wheel':
                    crit_e_type = self._get_button_wheel_label_per_direction()
            return (crit_e, crit_e_type)

        op_le = self.op_dict['<=']
        axis_dict = {'left': 'x', 'right': 'x', 'up': 'y', 'down': 'y',
                     'vert': 'y', 'horiz': 'x', 'alldir': 'xy', None: 'xy'}
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

        # Read some default parameters from config file
        max_motion_mixed = read_trackpad_test_conf('max_motion_mixed',
                                                   self.conf_path)
        max_button_wheel_mixed = read_trackpad_test_conf(
            'max_button_wheel_mixed', self.conf_path)

        index = -1
        crit_e_type = None
        keep_prev_crit = False
        # Handle boundary condition when work_xevent_seq is empty
        fail_msg = '%s'
        fail_para = '(empty work_xevent_seq)'
        for e in work_xevent_seq:
            e_type = e[0]
            e_value = e[1]
            fail_msg = None
            if crit_e_type != '*':
                if keep_prev_crit:
                    keep_prev_crit = False
                else:
                    index += 1
            (crit_e, crit_e_type) = _get_criteria(index, work_crit_sequence)

            # When there is no detected motion, skip the motion criteria if any
            # and get next criteria in the sequence.
            if (not e_type.startswith('Motion') and
                crit_e_type.startswith('Motion')):
                index += 1
                (crit_e, crit_e_type) = _get_criteria(index, work_crit_sequence)

            # Pass this event if the criteria is a wildcard
            if crit_e_type == '*':
                pass
            # Handle the situation that e_type not equal to crit_e_type
            elif not crit_e_type.startswith(e_type):
                keep_prev_crit = True
                if e_type.startswith('Motion'):
                    motion_val = e_value[0]
                    if motion_val > max_motion_mixed:
                        fail_msg = '%s (%d) is not allowed.'
                        fail_para = (e_type, motion_val)
                        break
                elif e_type.startswith('Button '):
                    if e_value > max_button_wheel_mixed:
                        fail_msg = '%s (%d) is not allowed'
                        fail_para = (e_type, e_value)
                        break
                else:
                    fail_msg = '%s (%s) is not allowed'
                    fail_para = (e_type, str(e_value))
                    break
            # Handle Motion event
            elif e_type.startswith('Motion'):
                motion_val = e_value[0]
                motion_x_val = e_value[1][1]
                motion_y_val = e_value[2][1]
                motion_xy_val = motion_x_val + motion_y_val
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
                        axis = axis_dict[self._get_general_direction()]
                        motion_axis_dict = {'x': {'this': motion_x_val,
                                                  'other': motion_y_val},
                                            'y': {'this': motion_y_val,
                                                  'other': motion_x_val},
                                            'xy': {'this': motion_xy_val,
                                                   'other': motion_xy_val},
                                           }
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
                                            op_le(motion_other_val,
                                                  bound_other_axis))

                        # If this axis is 'x', movement in 'y' should be small.
                        # If this axis is 'y', movement in 'x' should be small.
                        # If this axis is 'xy', no need to check the other axis.
                        crit_check = (check_this_axis and
                                      (axis == 'xy' or check_other_axis))
                        if not crit_check:
                            fail_msg = ('%s %s does not satisfy %s. '
                                        'Check motion for this axis = %s. '
                                        'Check motion for the other axis = %s')
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
            # Handle button events for Button Left/Middle/Right
            elif (e_type == crit_e_type == 'ButtonPress' or
                  e_type == crit_e_type == 'ButtonRelease'):
                # Check if the button label matches criteria
                if e_value != crit_e[1]:
                    fail_msg = 'Button %s does not match %s.'
                    fail_para = (e_value, crit_e[1])
                    break
            elif e_type == crit_e_type == NOP.NOP:
                pass
            # Handle 'Button Wheel' and 'Button Horiz Wheel' scroll events
            elif e_type.startswith('Button ') and e_type == crit_e_type:
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
        if fail_msg is None and index < len(work_crit_sequence) - 1:
            # Pass if the rest of criteria are trivial ones such as
            #       'Motion <= ...'
            #       'Button Wheel <= ...'
            index += 1
            trivial_op_list = ['<', '<=']
            for i in range(index, len(work_crit_sequence)):
                (crit_e, crit_e_type) = _get_criteria(index, work_crit_sequence)
                if (crit_e_type.startswith('Motion') or
                    crit_e_type.startswith('Button ')):
                    crit_e_op = crit_e[1]
                    if crit_e_op not in trivial_op_list:
                        fail_msg = ('Some events are missing compared to the '
                                    'criteria: %s.')
                        fail_para = str(crit_sequence)
                        break

        if fail_msg is not None:
            self.seq_flag = False

        self.vlog.verify_sequence_log(self.seq_flag, self.xevent.xevent_seq,
                                      fail_msg, fail_para)

    def _verify_button_segment(self, crit_button_segment):
        ''' Verify if a button event segment satisfies criteria

        This button_segment criteria allows to specify the interleaving of
        various device events in a bracketing X Button events between
        ButtonPress and ButtonRelease. This criteria is usually used
        for select and drag gesture with or without trackpad clicking.

        For example, the following event subsequence matches
        crit_button_segment.
        event sequence looks like: [
                         ...
                         ('NOP', 'Device Mouse Click Press'),
                         ('Motion', 10),
                         ('ButtonPress', 'Button Left'),
                         ('Motion', 68),
                         ('NOP', 'Device Mouse Click Release'),
                         ('ButtonRelease', 'Button Left')]
                         ...
        'crit_button_segment' : (
            ('NOP', ('Device Mouse Click Press', 'before', True)),
            ('NOP', ('Device Mouse Click Press', 'between', False)),
            ('NOP', ('Device Mouse Click Release', 'between', True)),
            ('Button', 'Button Left'),
            ('Motion', '>=', select_drag_distance),
        ),
        '''

        def _init_button_seg_events(self, nop_init_value=False,
                                    button_init_value=None,
                                    motion_init_value=0):
            ''' Initialize button_seg_events '''
            button_seg_events = {}
            # Initialize device event flag
            button_seg_events['accept_1st_gesture_only'] = False
            button_seg_events[NOP.NOP] = {}
            for d in self.button_segment_dev_event_list:
                button_seg_events[NOP.NOP][d] = {}
                for w in self.where_list:
                    button_seg_events[NOP.NOP][d][w] = nop_init_value
            button_seg_events['Button'] = button_init_value
            for m in self.motion_list:
                button_seg_events[m] = motion_init_value
            return button_seg_events

        def _check_button_segment(self, button_seg_events,
                                  crit_button_seg_events):
            ''' Check if the button_seg_events conform to the criteria '''
            flag = _init_button_seg_events(self, nop_init_value=False,
                                           button_init_value=False,
                                           motion_init_value=False)
            result = True
            fail_causes = []

            # Check device events
            for d in self.button_segment_dev_event_list:
                for w in self.where_list:
                    this_ev = button_seg_events[NOP.NOP][d][w]
                    flag[NOP.NOP][d][w] = (this_ev ==
                                         crit_button_seg_events[NOP.NOP][d][w])
                    if not flag[NOP.NOP][d][w]:
                        msg = 'NOP[%s][%s]: %s' % (d, w, this_ev)
                        fail_causes.append(msg)

            # Check button event
            flag['Button'] = (button_seg_events['Button'] ==
                              crit_button_seg_events['Button'])
            if not flag['Button']:
                msg = 'button: %s' % button_seg_events['Button']
                fail_causes.append(msg)

            # Check Motion events
            for m in self.motion_list:
                op_str, val = crit_button_seg_events[m]
                op = self.op_dict[op_str]
                flag[m] = op(button_seg_events[m], val)
                if not flag[m]:
                    msg = '%s: %s' % (m, button_seg_events[m])
                    fail_causes.append(msg)

            result = (len(fail_causes) == 0)
            return (result, '    Check Button Segment: %s', str(fail_causes))

        def _parse_button_seg_criteria(self):
            ''' Parse the button_segment criteria '''
            crit_button_seg_events = _init_button_seg_events(self,
                                            motion_init_value=('>=', 0))

            for c in crit_button_segment:
                name = c[0]
                if name == NOP.NOP:
                    # E.g.,('NOP', ('Device Mouse Click Press', 'before', True))
                    name, (dev_event, where, value) = c
                    crit_button_seg_events[name][dev_event][where] = value
                elif name == 'Button':
                    # E.g., ('bracket', 'Button Left')
                    name, button = c
                    crit_button_seg_events[name] = button
                elif name.startswith('Motion'):
                    # E.g., ('Motion', '>=', 20),
                    # E.g., ('Motion_x', '>=', 20),
                    # E.g., ('Motion_y', '<=', 0),
                    name, op, value = c
                    crit_button_seg_events[name] = (op, int(value))
                elif name == 'accept_1st_gesture_only':
                    name, value = c
                    crit_button_seg_events[name] = value

            return crit_button_seg_events

        # Some initialization
        where = 'before'
        fail_msg = '%s'
        fail_para = None
        self.button_seg_flag = False
        self.button_segment_dev_event_list = ['Device Mouse Click Press',
                                              'Device Mouse Click Release']
        self.where_list = ['before', 'between']
        button_seg_events = _init_button_seg_events(self)

        # Parse the criteria into a dictionary
        crit_button_seg_events = _parse_button_seg_criteria(self)

        # Match the xevent sequence against the criteria dictionary
        xevent_seq = self.xevent.xevent_seq
        for ev in xevent_seq:
            name = ev[0]
            if name == 'ButtonPress':
                # E.g., ('ButtonPress', 'Button Left', 443854733)
                name, button, timestamp = ev
                button_seg_events['Button'] = button
                where = 'between'
                for m in self.motion_list:
                    button_seg_events[m] = 0

            elif name == 'ButtonRelease':
                # E.g, ('ButtonRelease', 'Button Left', 443854884)
                name, button_release, timestamp = ev
                if button_release == button_seg_events['Button']:
                    check_results = _check_button_segment(self,
                                    button_seg_events, crit_button_seg_events)
                    self.button_seg_flag, fail_msg, fail_para = check_results
                    if (self.button_seg_flag or
                        crit_button_seg_events['accept_1st_gesture_only']):
                        break
                    where = 'before'
                    button_seg_events = _init_button_seg_events(self)
                else:
                    fail_msg = ('ButtonRelease of "%s" is not consistent with '
                                'ButtonPress of "%s".')
                    fail_para = (button_release, button)
                    break

            elif name == NOP.NOP:
                # E.g., ('NOP', 'Device Mouse Click Press')
                #       ('NOP', 'Device Mouse Click Release')
                name, dev_event, timestamp = ev
                button_seg_events[name][dev_event][where] = True

            elif name == 'Motion':
                # E.g., ('Motion', (655.0, ('Motion_x', 605), ('Motion_y', 20)),
                #                  [443855715, 443858536])
                (name, (motion_val, (_, motion_x_val), (_, motion_y_val)),
                 timestamp) = ev
                button_seg_events['Motion'] = int(motion_val)
                button_seg_events['Motion_x'] = int(motion_x_val)
                button_seg_events['Motion_y'] = int(motion_y_val)

        self.vlog.verify_button_segment_log(self.button_seg_flag, xevent_seq,
                                            fail_msg, fail_para)

    def _verify_all_criteria(self):
        ''' A general verification method for all criteria

        This is the core method invoked for every functionality. What to check
        is based on the criteria specified for the functionality in the
        config file.
        '''
        # A dictionary mapping criterion to its verification method
        criteria_method = {'total_movement': self._verify_motion,
                           'button': self._verify_button,
                           'button_dev': self._verify_button_with_device_events,
                           'delay': self._verify_select_delay,
                           'wheel_speed': self._verify_wheel_speed,
                           'sequence': self._verify_select_sequence,
                           'button_segment': self._verify_button_segment,
                          }

        # The result flags of performing the above verification methods
        self._set_result_flags()

        # Insert NOP based on criteria
        self._insert_nop_per_criteria(criteria_method)

        debug('    xevent_data:', level=1)
        for x in self.xevent.xevent_data:
            debug('          %s' % x, level=1)

        # Parse X button and motion events and aggregate the results.
        self.xevent.parse_button_and_motion()

        # Check those criteria specified in the config file.
        for c in criteria_method:
            crit = self._match_criteria_with_subname(c)
            if crit is not None:
                crit_item = self.criteria[crit]
                criteria_method[c](crit_item)

        # AND all results of various criteria.
        self._get_result()

    def run(self, tp_func, tp_data, xevent_str):
        ''' Parse the x events and invoke a proper check function

        Invoke the corresponding check function based on its functionality name.
        For example, tp_func.name == 'no_cursor_wobble' will result in the
        invocation of self._check_no_cursor_wobble()
        '''
        parse_result = self.xevent.parse_raw_string(xevent_str)
        self.gesture_file_name = tp_data.file_basename
        self.func_name_pos = 0 if tp_data.prefix is None else 1
        self.criteria = tp_func.criteria
        self.vlog = trackpad_util.VerificationLog()
        if parse_result:
            self._verify_all_criteria()
            return {'result': self.result, 'vlog': self.vlog.log}
        else:
            return False
