# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
import logging
import subprocess

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error


class touch_playback_test_base(test.test):
    """Base class for touch tests involving playback."""
    version = 1

    _PLAYBACK_COMMAND = 'evemu-play --insert-slot0 %s < %s'
    _INPUTCONTROL = '/opt/google/input/inputcontrol'

    _TOUCH_TYPES = ['touchpad', 'touchscreen', 'mouse']

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

    def warmup(self, mouse_props=None, mouse_name=None):
        """Determine the nodes of all present touch devices, if any.

        Use inputcontrol command to get the touch ids and xinput to get the
        corresponding node numbers.  These numbers are used for playback.
        Emulate a USB mouse if a property file is provided.

        @param mouse_props: property file for a mouse to emulate.  Created
                            using 'evemu-describe /dev/input/X'.
        @param mouse_name: name of expected mouse.

        """
        name_cmd = '%s --names -t %s' % (self._INPUTCONTROL, '%s')
        type_cmd = name_cmd + ' | grep "%s" | cut -d : -f 1'
        node_cmd = ('DISPLAY=:0 XAUTHORITY=/home/chronos/.Xauthority '
                    'xinput list-props %s '
                    '| grep dev/input | cut -d \'"\' -f 2')

        self._has_inputs = defaultdict(bool)
        self._nodes = defaultdict(str)
        self._names = defaultdict(str)
        self._device_emulation_process = None

        # Emulate mouse if property file was provided.
        if mouse_props:
            self._device_emulation_process = subprocess.Popen(
                    ['evemu-device', mouse_props], stdout=subprocess.PIPE)
            self._names['mouse'] = mouse_name
        for input_type in self._TOUCH_TYPES:
            id_num = utils.run(type_cmd % (
                    input_type, self._names[input_type])).stdout.strip()
            if id_num:
                self._has_inputs[input_type] = True
                self._nodes[input_type] = utils.run(
                        node_cmd % id_num).stdout.strip()
                name = utils.run(name_cmd % input_type).stdout.strip()
                logging.info('Found %s named %s at node %s', input_type,
                             name, self._nodes[input_type])

        logging.info('This DUT has the following input devices:')
        logging.info(
                utils.run('%s --names' % self._INPUTCONTROL).stdout.strip())


    def _playback(self, filepath, touch_type='touchpad'):
        """Playback a given set of touch movements.

        @param filepath: path to the movements file on the DUT.
        @param touch_type: name of device type; 'touchpad' by default.  String
                           must be in self._TOUCH_TYPES list.

        """
        assert(touch_type in self._TOUCH_TYPES)
        node = self._nodes[touch_type]
        logging.info('Playing back finger-movement on %s, file=%s.', node,
                     filepath)
        utils.run(self._PLAYBACK_COMMAND % (node, filepath))

    def _set_australian_scrolling(self, value):
        """Set australian scrolling to the given value.

        @param value: True for enabled, False for disabled.

        """
        cmd_value = 1 if value else 0
        utils.run('%s --australian_scrolling %d' % (self._INPUTCONTROL,
                                                    cmd_value))
        logging.info('Australian scrolling turned %s.',
                     'on' if value else 'off')

    def cleanup(self):
        if self._device_emulation_process:
            self._device_emulation_process.kill()


    def _get_scroll_position(self):
        """Return current scroll position of page.  Presuposes self._tab."""
        return int(self._tab.EvaluateJavaScript('document.body.scrollTop'))

    def _reset_scroll_position(self):
        """Reset page position to default.  Presuposes self._tab.

        @raise: TestError if page is not reset.

        """
        self._tab.ExecuteJavaScript('window.scrollTo(0, %d)'
                                    % self._DEFAULT_SCROLL)
        utils.poll_for_condition(
                lambda: self._get_scroll_position() == self._DEFAULT_SCROLL,
                exception=error.TestError('Default scroll was not set!'))

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

