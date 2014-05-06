# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

''' A module for parsing X events and manipulating X Button labels '''

import logging
import math
import os
import re

import constants
import trackpad_util

from common_util import simple_system, simple_system_output


# Declare X property names
X_PROP_SCROLL_BUTTONS = 'Scroll Buttons'
X_PROP_TAP_ENABLE = 'Tap Enable'

# Declare NOP as a instance containing NOP related constants
NOP = constants.NOP()


class Xinput(object):
    ''' Manipulation of xinput properties

    An example usage for instantiating a trackpad xinput device:
    xi = Xinput('t(?:ouch|rack)pad')
    '''

    def __init__(self, device_re_str):
        self.device_re_str = device_re_str
        self.xinput_str = 'DISPLAY=:0 xinput %s'

        # list command looks like
        #   DISPLAY=:0 xinput list
        self.xinput_list_cmd = self.xinput_str % 'list'
        self.dev_id = self.lookup_device_id()

        # list-props command looks like
        #   DISPLAY=:0 xinput list-props 11
        list_props_str = 'list-props %s' % self.dev_id
        self.xinput_list_props_cmd = self.xinput_str % list_props_str

    def device_exists(self):
        ''' Indicating whether the device exists or not. '''
        return self.dev_id is not None

    def lookup_device_id(self):
        ''' Look up device id with the specified device string

        For example, a trackpad device looks like
        SynPS/2 Synaptics TouchPad         id=11   [slave  pointer  (2)]
        '''
        dev_patt_str = '%s\s*id=(\d+)\s*\[' % self.device_re_str
        dev_patt = re.compile(dev_patt_str, re.I)
        dev_list = simple_system_output(self.xinput_list_cmd)
        if dev_list:
            for line in dev_list.splitlines():
                result = dev_patt.search(line)
                if result is not None:
                    return result.group(1)
        return None

    def lookup_int_prop_id_and_value(self, prop_name):
        ''' Look up integer property id based on property name

        For example, a property looks like
        Scroll Buttons (271):   0
        '''
        prop_re_str = '\s*%s\s*\((\d+)\):\s*(\d+)' % prop_name
        prop_patt = re.compile(prop_re_str, re.I)
        prop_list = simple_system_output(self.xinput_list_props_cmd)
        if prop_list:
            for line in prop_list.splitlines():
                result = prop_patt.search(line)
                if result:
                    return (result.group(1), int(result.group(2)))
        return (None, None)

    def set_int_prop_value(self, prop_id, prop_val):
        ''' Set integer property value

        For example, to enable Scroll Buttons (id=271) at device 11
        DISPLAY=:0 xinput set-prop 11 271 1
        '''
        # set-prop command looks like
        #   DISPLAY=:0 xinput set-prop 11 271 1
        set_int_prop_str = 'set-prop %s %s %d' % (self.dev_id, prop_id,
                                                  prop_val)
        self.xinput_set_int_prop_cmd = self.xinput_str % set_int_prop_str
        simple_system(self.xinput_set_int_prop_cmd)


class XIntProp(Xinput):
    ''' A special class to manipulate xinput Int Property. '''

    def __init__(self, prop_name):
        ''' Look up the id and value of the X int property '''
        self.name = prop_name
        super(XIntProp, self).__init__(self._get_trackpad_re_str())
        # Look up the property only when the device exists
        if self.device_exists():
            prop_result = self.lookup_int_prop_id_and_value(prop_name)
            self.prop_id, self.orig_prop_val = prop_result
        else:
            self.prop_id = self.orig_prop_val = None

    def _get_trackpad_re_str(self):
        xinput_trackpad_string = trackpad_util.read_trackpad_test_conf(
            'xinput_trackpad_string', '.')
        return '(?:%s)' % '|'.join(xinput_trackpad_string)

    def exists(self):
        ''' Indicating whether the property exists or not. '''
        return self.prop_id is not None

    def set_prop(self):
        ''' Enable the int property if it is not enabled yet. '''
        if self.orig_prop_val == 0:
            self.set_int_prop_value(self.prop_id, 1)

    def reset_prop(self):
        ''' Disable the int property if it was originally disabled. '''
        if self.orig_prop_val == 0:
            self.set_int_prop_value(self.prop_id, 0)


def set_x_input_prop(prop_name):
    ''' Enable the specified property if it is not enabled yet. '''
    prop = XIntProp(prop_name)
    if prop.exists():
        prop.set_prop()
        logging.info('  The property %s has been set.' % prop_name)
    else:
        logging.info('  The property %s does not exist.' % prop_name)
    return prop


def reset_x_input_prop(prop):
    ''' Disable the specified property if it was originally disabled. '''
    if prop.exists():
        prop.reset_prop()
        logging.info('  The property %s has been reset.' % prop.name)


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
    DEFAULT_BUTTON_LABELS = ('Button Left', 'Button Middle', 'Button Right',
                             'Button Back', 'Button Forward')

    def __init__(self):
        self.display_environ = trackpad_util.Display().get_environ()
        self.xinput_list_cmd = ' '.join([self.display_environ, 'xinput list'])
        self.xinput_dev_cmd = ' '.join([self.display_environ,
                                        'xinput list --long %s'])
        self.trackpad_dev_id = self._get_trackpad_dev_id()
        self.button_labels = None
        self.get_supported_buttons()

    def _get_trackpad_dev_id(self):
        trackpad_dev_id = None
        if os.system('which xinput') == 0:
            input_dev_str = simple_system_output(self.xinput_list_cmd)
            for dev_str in input_dev_str.splitlines():
                res = re.search(r'(t(ouch|rack)pad.+id=)(\d+)', dev_str, re.I)
                if res is not None:
                    trackpad_dev_id = res.group(3)
                    break
        return trackpad_dev_id

    def get_supported_buttons(self):
        ''' Get supported button labels from xinput

        a device returned from 'xinput list' looks like:
        |   SynPS/2 Synaptics TouchPad       id=11   [slave  pointer (2)]

        Button labels returned from 'xinput list <device_id>' looks like:
        Button labels: Button Left Button Middle Button Right Button Wheel Up
        Button Wheel Down Button Horiz Wheel Left Button Horiz Wheel Right
        Button 0 Button 1 Button 2 Button 3 Button 4 Button 5 Button 6
        Button 7
        '''

        if self.button_labels is not None:
            return self.button_labels

        if self.trackpad_dev_id is not None:
            xinput_dev_cmd = self.xinput_dev_cmd % self.trackpad_dev_id
            features = simple_system_output(xinput_dev_cmd)
            # The Button labels line looks like
            #     Button labels: "Button Left" "Button Middle" "Button Right"
            #                    "Button Back" "Button Forward"
            if features is not None:
                for line in features.splitlines():
                    if line.lstrip().startswith('Button labels:'):
                        button_labels_str = line.lstrip('Button labels:')
                        self.button_labels = [
                                b for b in button_labels_str.split('"')
                                if b.startswith('Button')]

        if self.button_labels is None:
            logging.warn('Cannot find trackpad device in xinput. '
                         'Using default Button Labels instead.')
            self.button_labels = self.DEFAULT_BUTTON_LABELS

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
        self.motion_trace_before = trackpad_util.read_trackpad_test_conf(
            'motion_trace_before', '.')
        self.motion_trace_after = trackpad_util.read_trackpad_test_conf(
            'motion_trace_after', '.')
        self.LONG_MOTIOIN_TRACE = trackpad_util.read_trackpad_test_conf(
            'LONG_MOTION_TRACE', '.')

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

        if not xevent_str:
            logging.warn('    No X events were captured.')
            return False

        xevent_iter = iter(xevent_str)
        self.xevent_data = []
        while True:
            line = next(xevent_iter, None)
            if line is None:
                break
            line_words = line.split()
            if not line_words:
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

        def _reset_coord():
            return [None, None]

        def _add_seg_move(seg_move, move):
            ''' Accumulate seg_move in x+y, x, and y respectively '''
            list_add = lambda list1, list2: map(sum, zip(list1, list2))
            return [seg_move[0] + move[0], list_add(seg_move[1], move[1])]

        def _is_finger_off(line):
            ''' Is finger off the trackpad? '''
            ev_name, ev_dict = line
            if isinstance(ev_dict, dict) and ev_dict.has_key('event'):
                return ev_dict['event'] == 'Finger Off'

        def _reset_motion_trace(self):
            ''' Reset motion_trace and its state '''
            self.motion_trace_state = None
            self.motion_trace = []
            self.motion_trace_len = self.LONG_MOTIOIN_TRACE

        def _extract_motion_trace_state(self, line):
            ''' Extract motion_trace_state which determines motion trace
            length and buffer strategy.

            For typical physical clicks:
            ----------------------------
              Finger On

                  optional Motion events        Use trace: motion_trace_before
                Device Mouse Click Press
                  optional Motion events
                ButtonPress
                  optional Motion events
                Device Mouse Click Release
                  optional Motion events
                ButtonRelease
                  optional Motion events        Use trace: motion_trace_after

                  optional Motion events        Use trace: motion_trace_before
                Device Mouse Click Press
                  optional Motion events
                ButtonPress
                  optional Motion events
                Device Mouse Click Release
                  optional Motion events
                ButtonRelease
                  optional Motion events        Use trace: motion_trace_after

                  ...

              Finger Off

            (1) state == 'Finger On':
                Set trace length: LONG_MOTIOIN_TRACE
                Note: its next state could be either 'Device Mouse Click Press'
                      or 'ButtonPress'.
                motion_trace_state = state

            (2) state == 'Device Mouse Click Press':
                Set trace length: motion_trace_before
                Motion report: Use only the motion_trace_before portion in
                               motion_trace.
                Reason: Users may move cursor around and, without finger
                        leaving trackpad, make a physical click. We do not want
                        to take into account the cursor movement during
                        finger tracking.
                Set trace length: LONG_MOTIOIN_TRACE
                motion_trace_state = state

            (3) state == 'ButtonPress':
                Motion report: Use all motion events in motion_trace
                               since it is in the middle of a physical click.
                Note: its previoius state could be either 'Device Mouse Click
                      Press' or 'Finger On'
                Set trace length: LONG_MOTIOIN_TRACE
                motion_trace_state = state

            (4) state == 'Device Mouse Click Release':
                (No need to handle 'Device Mouse Click Release' explicitly)

            (5) state == 'ButtonRelease':
                Motion report: Use all motion events in motion_trace
                               since it is in the middle of a physical click.
                Set trace length: motion_trace_after
                Reason: After releasing the physical click, without finger
                        leaving trackpad, users may move cursor around. So we
                        only want to collect the motion events afterwards in
                        limited time.
                Note: After motion_trace_after has been collected.
                      Append a motion report. And then turn to using
                      "Set trace length: LONG_MOTIOIN_TRACE"
                                          for next possible clicks or
                                          tap-to-clicks.
                motion_trace_state = state

            (6) state == 'Finger Off':
                if self.motion_trace_state == 'ButtonRelease':
                    Motion report: Use motion events in the motion_trace
                                   for up to motion_trace_after elements.
                Set trace length: LONG_MOTIOIN_TRACE
                motion_trace_state = state

            (7) event_name == 'Motion':
                if (self.motion_trace_state == 'ButtonRelease' and
                    len(self.motion_trace) >= self.motion_trace_len - 1):
                    _append_motion(self)
                    self.motion_trace_len = self.LONG_MOTIOIN_TRACE
                    self.motion_trace_state = 'ButtonRelease.TraceAfterDone'
                    Note: Next state could be either 'Device Mouse Click Press'
                          or 'Finger Off'
            '''
            ev_name, ev_dict = line
            state = None
            if ev_name in ['ButtonPress', 'ButtonRelease', 'MotionNotify']:
                state = ev_name
            elif (ev_name == 'NOP' and
                  ev_dict['event'] in ['Finger On', 'Finger Off',
                                       'Device Mouse Click Press']):
                state = ev_dict['event']
            return state

        def _insert_motion_trace_entry(self, event_coord, event_time):
            # Insert an entry into motion_trace
            mtrace_dict = {'coord': event_coord, 'time': event_time}
            self.motion_trace.append(mtrace_dict)

            if len(self.motion_trace) > self.motion_trace_len:
                self.motion_trace.pop(0)

        def _reduce_motion_trace(self, target_trace_len):
            # Reduce motion_trace according to target_trace_len
            trace_len = len(self.motion_trace)
            if trace_len > target_trace_len:
                begin_index = trace_len - target_trace_len
                self.motion_trace = self.motion_trace[begin_index:]

        def _add_motion_trace(self, event_coord, event_time, line):
            ''' Add the new coordinate into motion_trace.

            If the trace lenght exceeds a predefined length, pop off the
            oldest entry from the trace buffer.

            Refer to _extract_motion_trace_state() for details about
            the operations of motion_trace.
            '''
            state = _extract_motion_trace_state(self, line)

            # Determine motion trace length based on motion trace state
            if state == 'Finger On':
                self.motion_trace_len = self.LONG_MOTIOIN_TRACE
                self.motion_trace_state = state

            elif state == 'Device Mouse Click Press':
                _reduce_motion_trace(self, self.motion_trace_before)
                _append_motion(self)
                self.motion_trace_len = self.LONG_MOTIOIN_TRACE
                self.motion_trace_state = state

            elif state == 'ButtonPress':
                _insert_motion_trace_entry(self, event_coord, event_time)
                _append_motion(self)
                self.motion_trace_len = self.LONG_MOTIOIN_TRACE
                self.motion_trace_state = state

            elif state == 'ButtonRelease':
                _insert_motion_trace_entry(self, event_coord, event_time)
                _append_motion(self)
                self.motion_trace_len = self.motion_trace_after
                self.motion_trace_state = state

            elif state == 'Finger Off':
                # if the state is not 'ButtonRelease.TraceAfterDone' yet
                if self.motion_trace_state == 'ButtonRelease':
                    _append_motion(self)
                self.motion_trace_len = self.LONG_MOTIOIN_TRACE
                self.motion_trace_state = state

            elif state == 'MotionNotify':
                _insert_motion_trace_entry(self, event_coord, event_time)
                if (self.motion_trace_state == 'ButtonRelease' and
                    len(self.motion_trace) >= self.motion_trace_len - 1):
                    _append_motion(self)
                    self.motion_trace_len = self.LONG_MOTIOIN_TRACE
                    self.motion_trace_state = 'ButtonRelease.TraceAfterDone'

            elif line[0] == 'NOP':
                _append_motion(self)

        def _append_event(event):
            ''' Append the event into xevent_seq '''
            self.xevent_seq.append(event)
            indent = ' ' * 14
            logging.info(indent + str(event))

        def _append_motion(self):
            ''' Append Motion events to xevent_seq '''
            if not self.motion_trace:
                return

            # Compute the accumulated movement and the time span
            # in motion_trace buffer.
            pre_xy = _reset_coord()
            seg_move = _reset_seg_move()
            seg_time_span = [None, None]
            for m in self.motion_trace:
                cur_xy = m['coord']
                cur_time = m['time']
                if pre_xy == [None, None]:
                    pre_xy = cur_xy
                    seg_time_span = [cur_time, cur_time]
                else:
                    move = self._calc_distance(*(pre_xy + cur_xy))
                    seg_move = _add_seg_move(seg_move, move)
                    pre_xy = cur_xy
                    seg_time_span[1] = cur_time

            # Append the motion report data to xevent_seq
            # The format of reported motion data looks like:
            #   ('Motion', motion_data, time_span)
            #
            #   E.g.,
            #   ('Motion', (2.0, ('Motion_x', 2), ('Motion_y', 0)),
            #              [351613962, 351614138])
            (move_xy, (move_x, move_y)) = seg_move
            if move_x > 0 or move_y > 0:
                move_val = (move_xy, ('Motion_x', move_x), ('Motion_y', move_y))
                event = ('Motion', move_val, seg_time_span)
                _append_event(event)

            # Clear the motion_trace buffer and keep the last entry
            last_entry = self.motion_trace.pop()
            _reset_motion_trace(self)
            self.motion_trace.append(last_entry)

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
            if event_name == NOP.NOP:
                event = (event_name, event_description, event_time)
                _append_event(event)

        self.count_buttons = self.xbutton.init_button_struct(0)
        self.seg_count_buttons = self.xbutton.init_button_struct(0)
        self.count_buttons_press = self.xbutton.init_button_struct(0)
        self.count_buttons_release = self.xbutton.init_button_struct(0)
        self.button_states = self.xbutton.init_button_struct('ButtonRelease')

        pre_xy = _reset_coord()
        button_label = pre_button_label = None
        event_name = None
        event_button = pre_event_button = None
        self.xevent_seq = []
        seg_move_time = _reset_time_interval()
        button_time = _reset_time_interval()
        self.sum_move = 0
        _reset_motion_trace(self)

        indent = ' ' * 8
        logging.info(indent + 'X events detected:')

        for line in self.xevent_data:
            flag_finger_off = _is_finger_off(line)
            event_name = line[0]
            event_coord = _reset_coord()
            event_time = None
            if event_name != NOP.NOP:
                event_dict = line[1]
                if event_dict.has_key('coord'):
                    event_coord = list(eval(event_dict['coord']))
                if event_dict.has_key('button'):
                    event_button = eval(event_dict['button'])
                if event_dict.has_key('time'):
                    event_time = eval(event_dict['time'])

            # _extract_motion_trace_state(self, line)
            _add_motion_trace(self, event_coord, event_time, line)

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
                    self.sum_move += move[0]

                if seg_move_time[0] is None:
                    seg_move_time = [event_time, event_time]
                else:
                    seg_move_time[1] = event_time

            elif event_name.startswith('Button'):
                seg_move_time = _reset_time_interval()
                button_label = self.xbutton.get_label(event_button)
                self.button_states[event_button] = event_name

                if button_label == pre_button_label:
                    button_time[1] = event_time
                else:
                    # Append Button Wheel count when event button is changed
                    _append_button_wheel(pre_button_label, pre_event_button,
                                         button_time)
                    self.seg_count_buttons = self.xbutton.init_button_struct(0)
                    button_time = _reset_time_interval(begin_time=event_time)

                # Append button events except button wheel events
                _append_button(event_name, button_label, event_time)

                # A ButtonRelease should precede ButtonPress
                # A ButtonPress should precede ButtonRelease
                if event_name == 'ButtonPress':
                    self.count_buttons_press[event_button] += 1
                elif event_name == 'ButtonRelease':
                    self.count_buttons_release[event_button] += 1
                self.count_buttons[event_button] += 0.5
                self.seg_count_buttons[event_button] += 0.5
                pre_button_label = button_label
                pre_event_button = event_button

            elif event_name == NOP.NOP:
                _append_button_wheel(pre_button_label, pre_event_button,
                                     button_time)
                pre_button_label = None
                self.seg_count_buttons = self.xbutton.init_button_struct(0)
                button_time = _reset_time_interval()
                seg_move_time = _reset_time_interval()
                _append_NOP(NOP.NOP, line[1]['event'], line[1]['time'])
                if flag_finger_off:
                    pre_xy = _reset_coord()
                    _reset_motion_trace(self)

        # Append aggregated button wheel events and motion events
        _append_button_wheel(button_label, event_button, button_time)
        _append_motion(self)

        # Convert dictionary to tuple
        self.button_states = tuple(self.button_states.values())
        self.count_buttons = tuple(self.count_buttons.values())
