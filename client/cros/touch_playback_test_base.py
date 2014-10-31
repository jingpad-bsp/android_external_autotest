# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
import logging
import os
import tempfile
import subprocess

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error


class touch_playback_test_base(test.test):
    """Base class for touch tests involving playback."""
    version = 1

    _PLAYBACK_COMMAND = 'evemu-play --insert-slot0 %s < %s'
    _INPUTCONTROL = '/opt/google/input/inputcontrol'
    _DEFAULT_SCROLL = 5000

    @property
    def _has_touchpad(self):
        """True if device under test has a touchpad; else False."""
        return self._has_inputs['touchpad']

    @property
    def _has_touchscreen(self):
        """True if device under test has a touchscreen; else False."""
        return self._has_inputs['touchscreen']

    @property
    def _has_mouse(self):
        """True if device under test has or emulates a USB mouse; else False."""
        return self._has_inputs['mouse']

    def _find_device_properties(self, device):
        """Given device (e.g. /dev/input/event7), return a string of properties.

        @return: string of properties.

        """
        temp_file = tempfile.NamedTemporaryFile()
        filename = temp_file.name
        evtest_process = subprocess.Popen(['evtest', device], stdout=temp_file)

        def find_exit():
            """Polling function for end of output."""
            interrupt_cmd = 'grep "interrupt to exit" %s | wc -l' % filename
            line_count = utils.run(interrupt_cmd).stdout.strip()
            return line_count != '0'

        utils.poll_for_condition(find_exit)
        evtest_process.kill()
        temp_file.seek(0)
        props = temp_file.read()
        temp_file.close() #deletes the temporary file
        return props

    def _determine_input_type(self, event):
        """Find event's list of propertiles and return input type (if any)."""
        props = self._find_device_properties(event)
        if props.find('REL_X') >= 0 and props.find('REL_Y') >= 0:
            if (props.find('ABS_MT_POSITION_X') >= 0 and
                props.find('ABS_MT_POSITION_Y') >= 0):
                return 'multitouch_mouse'
            else:
                return 'mouse'
        if props.find('ABS_X') >= 0 and props.find('ABS_Y') >= 0:
            if (props.find('BTN_STYLUS') >= 0 or
                props.find('BTN_STYLUS2') >= 0 or
                props.find('BTN_TOOL_PEN') >= 0):
                return 'tablet'
            if (props.find('ABS_PRESSURE') >= 0 or
                props.find('BTN_TOUCH') >= 0):
                if (props.find('BTN_LEFT') >= 0 or
                    props.find('BTN_MIDDLE') >= 0 or
                    props.find('BTN_RIGHT') >= 0 or
                    props.find('BTN_TOOL_FINGER') >= 0):
                    return 'touchpad'
                else:
                    return 'touchscreen'
            if props.find('BTN_LEFT') >= 0:
                return 'touchscreen'
        return

    def warmup(self, mouse_props=None, mouse_name=''):
        """Determine the nodes of all present touch devices, if any.

        Cycle through all possible /dev/input/event* and find which ones
        are touchpads, touchscreens, mice, etc.
        These events can be used for playback later.
        Emulate a USB mouse if a property file is provided.

        @param mouse_props: property file for a mouse to emulate.  Created
                            using 'evemu-describe /dev/input/X'.
        @param mouse_name: name of expected mouse.

        """
        self._has_inputs = defaultdict(bool)
        self._nodes = defaultdict(str)
        self._names = defaultdict(str)
        self._device_emulation_process = None

        # Emulate mouse if property file was provided.
        if mouse_props:
            logging.info('Emulating mouse: %s', mouse_props)
            self._device_emulation_process = subprocess.Popen(
                    ['evemu-device', mouse_props], stdout=subprocess.PIPE)
            self._names['mouse'] = mouse_name

        # Cycle through all possible input devices.
        input_events = utils.run('ls /dev/input/event*').stdout.strip().split()
        for event in input_events:
            input_type = self._determine_input_type(event)
            if input_type:
                logging.info('Found %s at %s.', input_type, event)

                class_folder = event.replace('dev', 'sys/class')
                name_file = os.path.join(class_folder, 'device', 'name')
                name = 'unknown'
                if os.path.isfile(name_file):
                    name = utils.run('cat %s' % name_file).stdout.strip()
                # If a particular device is expected, make sure this matches.
                if self._names[input_type]:
                    if self._names[input_type] != name:
                        continue

                # Save this device information for later use.
                self._has_inputs[input_type] = True
                self._nodes[input_type] = event
                self._names[input_type] = name
                logging.info('%s is %s.', input_type, name)


    def _playback(self, filepath, touch_type='touchpad'):
        """Playback a given set of touch movements.

        @param filepath: path to the movements file on the DUT.
        @param touch_type: name of device type; 'touchpad' by default.
                           Types are returned by the _determine_input_type()
                           function.
                           self._has_inputs[touch_type] must be True.

        """
        assert(self._has_inputs[touch_type])
        node = self._nodes[touch_type]
        logging.info('Playing back finger-movement on %s, file=%s.', node,
                     filepath)
        utils.run(self._PLAYBACK_COMMAND % (node, filepath))

    def _set_touch_setting(self, setting, value):
        """Set a given touch setting the given value.

        @param setting: Name of touch setting, e.g. 'tapclick'.
        @param value: True for enabled, False for disabled.

        """
        cmd_value = 1 if value else 0
        utils.run('%s --%s %d' % (self._INPUTCONTROL, setting, cmd_value))
        logging.info('%s turned %s.', setting, 'on' if value else 'off')

    def _set_australian_scrolling(self, value):
        """Set australian scrolling to the given value.

        @param value: True for enabled, False for disabled.

        """
        self._set_touch_setting('australian_scrolling', value)

    def _set_tap_to_click(self, value):
        """Set tap-to-click to the given value.

        @param value: True for enabled, False for disabled.

        """
        self._set_touch_setting('tapclick', value)

    def _set_tap_dragging(self, value):
        """Set tap dragging to the given value.

        @param value: True for enabled, False for disabled.

        """
        self._set_touch_setting('tapdrag', value)

    def cleanup(self):
        if self._device_emulation_process:
            self._device_emulation_process.kill()

    def _reload_page(self):
        """Reloads test page.  Presuposes self._tab.

        @raise: TestError if page is not reset.

        """
        self._tab.Navigate(self._tab.url)
        self._tab.WaitForDocumentReadyStateToBeComplete()

    def _get_scroll_position(self):
        """Return current scroll position of page.  Presuposes self._tab."""
        return int(self._tab.EvaluateJavaScript('document.body.scrollTop'))

    def _wait_for_default_scroll_position(self):
        """Wait for page to be the default scroll position.

        @raise: TestError if page either does not move or does not stop moving.

        """
        utils.poll_for_condition(
                lambda: self._get_scroll_position() == self._DEFAULT_SCROLL,
                exception=error.TestError('Page not set to default scroll!'))


    def _wait_for_scroll_position_to_settle(self):
        """Wait for page to move and then stop moving.

        @raise: TestError if page either does not move or does not stop moving.

        """
        # Wait until page starts moving.
        utils.poll_for_condition(
                lambda: self._get_scroll_position() != self._DEFAULT_SCROLL,
                exception=error.TestError('No scrolling occurred!'))

        # Wait until page has stopped moving.
        self._previous = self._DEFAULT_SCROLL
        def _movement_stopped():
            current = self._get_scroll_position()
            result = current == self._previous
            self._previous = current
            return result

        utils.poll_for_condition(
                lambda: _movement_stopped(), sleep_interval=1,
                exception=error.TestError('Page did not stop moving!'))

