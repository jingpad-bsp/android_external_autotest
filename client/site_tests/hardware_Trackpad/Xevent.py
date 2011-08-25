# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

''' A module for parsing X events and manipulating X Button labels '''

import logging
import math
import os
import re
import time
import utils

import trackpad_util


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
        self.button_labels = None
        self.get_supported_buttons()
        self.wheel_label_dict = {'up': self.get_label(XButton.Wheel_Up),
                                 'down': self.get_label(XButton.Wheel_Down),
                                 'left': self.get_label(XButton.Wheel_Left),
                                 'right': self.get_label(XButton.Wheel_Right),}

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
        if self.button_labels is not None:
            return self.button_labels

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

    def init_button_struct_with_time(self, value, time):
        ''' Initialize a button dictionary with time to the given values. '''
        return dict(map(lambda b: (self.get_value(b), [value, list(time)]),
                                  self.button_labels))

    def is_button_wheel(self, button_label):
        '''  Is this button a wheel button? '''
        return button_label in ['Button Wheel Up',
                                'Button Wheel Down',
                                'Button Horiz Wheel Left',
                                'Button Horiz Wheel Right']


class XEvent:
    ''' A class for X event parsing '''

    def __init__(self, xbutton):
        self.xbutton = xbutton
        # Declare the format to extract information from X event structures
        self.raw_format_dict = {
            'Motion_coord'  : '{6}',
            'Motion_time'   : '{5}',
            'Motion_tv'     : '{7}',
            'Button_coord'  : '{6}',
            'Button_button' : '{3}',
            'Button_time'   : '{5}',
            'Button_tv'     : '{7}',
        }

    def _extract_prop(self, event_name, line, prop_key):
        ''' Extract property from X events '''
        if line is None:
            logging.warn('      X event format may not be correct.')
            return None

        event_format_str = self.raw_format_dict[event_name]
        try:
            prop_val = event_format_str.format(*line.strip().split()).strip(',')
        except IndexError, err:
            logging.warn('      %s in X event data.' % str(err))
            return None
        return (prop_key, prop_val)

    def _calc_distance(self, x0, y0, x1, y1):
        ''' A simple Manhattan distance '''
        delta_x = abs(x1 - x0)
        delta_y = abs(y1 - y0)
        dist = round(math.sqrt(delta_x * delta_x + delta_y * delta_y))
        return [dist, [delta_x, delta_y]]

    def parse_raw_string(self, xevent_str):
        ''' Parse X raw event string

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
            if len(line_words) == 0:
                continue
            event_name = line_words[0]

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

    def parse_button_and_motion(self):
        ''' Parse X button events and motion events

        This method parses original X button events and motion events from
        self.xevent_data, and saves the aggregated results in self.xevent_seq

        The variable seg_move accumulates the motions of the contiguous events
        segmented by some boundary events such as Button events and other
        NOP events.

        A NOP (no operation) event is a fake X event which is used to indicate
        the occurrence of some important trackpad device events. It can be
        use to compute the latency between a device event and a resultant X
        event. It can also be used to partition X events into groups.
        '''

        # Define some functions for seg_move
        def _reset_seg_move():
            ''' Reset seg_move in x+y, x, and y to 0 '''
            return [0, [0, 0]]

        def _reset_time_interval(begin_time=None):
            ''' Reset time interval '''
            return [begin_time, None]

        def _add_seg_move(seg_move, move):
            ''' Accumulate seg_move in x+y, x, and y respectively '''
            list_add = lambda list1, list2: map(sum, zip(list1, list2))
            return [seg_move[0] + move[0], list_add(seg_move[1], move[1])]

        def _append_event(event):
            ''' Append the event into xevent_seq '''
            self.xevent_seq.append(event)
            indent = ' ' * 14
            logging.info(indent + str(event))

        def _append_motion(pre_event_name, seg_move, seg_move_time):
            ''' Append Motion events '''

            # Insert Motion events in the beginning and end of the xevent_seq
            begin_or_end_flag = self.motion_begin_flag or self.motion_end_flag
            self.motion_begin_flag = self.motion_end_flag = False

            if pre_event_name == 'MotionNotify' or begin_or_end_flag:
                event = ('Motion', (seg_move[0], ('Motion_x', seg_move[1][0]),
                                                 ('Motion_y', seg_move[1][1])),
                                   seg_move_time)
                _append_event(event)

        def _append_button(event_name, button_label, event_time):
            ''' Append non-wheel Buttons

            Typically, they include Button Left, Button Middle, Button Right,
            and other non-wheel buttons etc.

            TODO(josephsih): creating a event class, with more formalized,
            named members (name, details, time). Or, using a dict, ('name': ,
            'details':, 'time':).
            '''
            if not self.xbutton.is_button_wheel(button_label):
                event = (event_name, button_label, event_time)
                _append_event(event)

        def _append_button_wheel(button_label, event_button, button_time):
            ''' Append Button Wheel count '''
            if self.xbutton.is_button_wheel(button_label):
                count = self.seg_count_buttons[event_button]
                count = int(count) if count == int(count) else count
                if count > 0:
                    event = (button_label, count, button_time)
                    _append_event(event)

        def _append_NOP(event_name, event_description, event_time):
            ''' Append NOP event '''
            if event_name == 'NOP':
                event = (event_name, event_description, event_time)
                _append_event(event)

        self.count_buttons = self.xbutton.init_button_struct(0)
        self.seg_count_buttons = self.xbutton.init_button_struct(0)
        self.count_buttons_press = self.xbutton.init_button_struct(0)
        self.count_buttons_release = self.xbutton.init_button_struct(0)
        self.button_states = self.xbutton.init_button_struct('ButtonRelease')

        pre_xy = [None, None]
        button_label = pre_button_label = None
        event_name = pre_event_name = None
        event_button = pre_event_button = None
        self.xevent_seq = []
        seg_move = _reset_seg_move()
        seg_move_time = _reset_time_interval()
        button_time = _reset_time_interval()
        self.sum_move = 0
        self.motion_begin_flag = True
        self.motion_end_flag = False

        indent = ' ' * 8
        precede_state = {'ButtonPress': 'ButtonRelease',
                         'ButtonRelease': 'ButtonPress',}
        logging.info(indent + 'X events detected:')

        for line in self.xevent_data:
            event_name = line[0]
            if event_name != 'NOP':
                event_dict = line[1]
                if event_dict.has_key('coord'):
                    event_coord = list(eval(event_dict['coord']))
                if event_dict.has_key('button'):
                    event_button = eval(event_dict['button'])
                if event_dict.has_key('time'):
                    event_time = eval(event_dict['time'])

            if event_name == 'EnterNotify':
                if pre_xy == [None, None]:
                    pre_xy = event_coord
                    seg_move_time[0] = event_time
                self.seg_count_buttons = self.xbutton.init_button_struct(0)
                if seg_move_time[0] is None:
                    seg_move_time = [event_time, event_time]
                else:
                    seg_move_time[1] = event_time

            elif event_name == 'MotionNotify':
                if pre_xy == [None, None]:
                    pre_xy = event_coord
                else:
                    cur_xy = event_coord
                    move = self._calc_distance(*(pre_xy + cur_xy))
                    pre_xy = cur_xy
                    seg_move = _add_seg_move(seg_move, move)
                    self.sum_move += move[0]
                if seg_move_time[0] is None:
                    seg_move_time = [event_time, event_time]
                else:
                    seg_move_time[1] = event_time

            elif event_name.startswith('Button'):
                _append_motion(pre_event_name, seg_move, seg_move_time)
                seg_move = _reset_seg_move()
                seg_move_time = _reset_time_interval()
                button_label = self.xbutton.get_label(event_button)
                pre_button_state = self.button_states[event_button]
                self.button_states[event_button] = event_name

                # Append button events except button wheel events
                _append_button(event_name, button_label, event_time)

                if button_label == pre_button_label:
                    button_time[1] = event_time
                else:
                    # Append Button Wheel count when event button is changed
                    _append_button_wheel(pre_button_label, pre_event_button,
                                         button_time)
                    self.seg_count_buttons = self.xbutton.init_button_struct(0)
                    button_time = _reset_time_interval(begin_time=event_time)

                # A ButtonRelease should precede ButtonPress
                # A ButtonPress should precede ButtonRelease
                precede_flag = pre_button_state == precede_state[event_name]
                if event_name == 'ButtonPress':
                    self.count_buttons_press[event_button] += 1
                elif event_name == 'ButtonRelease':
                    self.count_buttons_release[event_button] += 1
                self.count_buttons[event_button] += 0.5
                self.seg_count_buttons[event_button] += 0.5
                pre_button_label = button_label
                pre_event_button = event_button
            elif event_name == 'NOP':
                _append_button_wheel(pre_button_label, pre_event_button,
                                     button_time)
                pre_button_label = None
                self.seg_count_buttons = self.xbutton.init_button_struct(0)
                button_time = _reset_time_interval()
                _append_motion(pre_event_name, seg_move, seg_move_time)
                seg_move = _reset_seg_move()
                seg_move_time = _reset_time_interval()
                _append_NOP('NOP', line[1], line[2])
            pre_event_name = event_name

        # Append aggregated button wheel events and motion events
        _append_button_wheel(button_label, event_button, button_time)
        self.motion_end_flag = True
        _append_motion(pre_event_name, seg_move, seg_move_time)

        # Convert dictionary to tuple
        self.button_states = tuple(self.button_states.values())
        self.count_buttons= tuple(self.count_buttons.values())
