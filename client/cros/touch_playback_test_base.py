# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils


class touch_playback_test_base(test.test):
    """Base class for touch tests involving playback."""
    version = 1

    _PLAYBACK_COMMAND = 'evemu-play --insert-slot0 %s < %s'
    _INPUTCONTROL = '/opt/google/input/inputcontrol'
    _DEFAULT_SCROLL = 100

    _TOUCH_TYPES = ['touchpad', 'touchscreen']

    @property
    def _has_touchpad(self):
        """True if device under test has a touchpad; else False."""
        return self._has_inputs['touchpad']

    @property
    def _has_touchscreen(self):
        """True if device under test has a touchscreen; else False."""
        return self._has_inputs['touchscreen']

    def warmup(self):
        """Determine the nodes of all present touch devices, if any.

        Use inputcontrol command to get the touch ids and xinput to get the
        corresponding node numbers.  These numbers are used for playback.

        """
        name_cmd = '%s --names -t %s' % (self._INPUTCONTROL, '%s')
        type_cmd = '%s | cut -d : -f 1' % name_cmd
        node_cmd = ('DISPLAY=:0 XAUTHORITY=/home/chronos/.Xauthority '
                    'xinput list-props %s '
                    '| grep dev/input | cut -d \'"\' -f 2')

        self._has_inputs = {}
        self._nodes = {}

        for input_type in self._TOUCH_TYPES:
            id_num = utils.run(type_cmd % input_type).stdout.strip()
            if id_num:
                self._has_inputs[input_type] = True
                self._nodes[input_type] = utils.run(
                        node_cmd % id_num).stdout.strip()
                name = utils.run(name_cmd % input_type).stdout.strip()
                logging.info('Found %s named %s at node %s', input_type,
                             name, self._nodes[input_type])
            else:
                self._has_inputs[input_type] = False
                self._nodes[input_type] = None

    def _playback(self, filepath, touch_type='touchpad'):
        """Playback a given set of touch movements.

        @param filepath: path to the movements file on the DUT.
        @param use_touchpad: true to use touchpad, false for touchscreen.

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
