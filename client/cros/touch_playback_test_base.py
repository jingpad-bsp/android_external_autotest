# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.input_playback import input_playback


class touch_playback_test_base(test.test):
    """Base class for touch tests involving playback."""
    version = 1

    _INPUTCONTROL = '/opt/google/input/inputcontrol'
    _DEFAULT_SCROLL = 5000

    @property
    def _has_touchpad(self):
        """True if device under test has a touchpad; else False."""
        return self.player.has('touchpad')

    @property
    def _has_touchscreen(self):
        """True if device under test has a touchscreen; else False."""
        return self.player.has('touchscreen')

    @property
    def _has_mouse(self):
        """True if device under test has or emulates a USB mouse; else False."""
        return self.player.has('mouse')

    def warmup(self, mouse_props=None):
        """Test setup.

        Instantiate player object to find touch devices, if any.
        These devices can be used for playback later.
        Emulate a USB mouse if a property file is provided.
        Check if the inputcontrol script is avaiable on the disk.

        @param mouse_props: optional property file for a mouse to emulate.
                            Created using 'evemu-describe /dev/input/X'.

        """
        self.player = input_playback.InputPlayback()
        if mouse_props:
            self.player.emulate(input_type='mouse', property_file=mouse_props)
        self.player.find_connected_inputs()

        self._autotest_ext = None
        self._has_inputcontrol = os.path.isfile(self._INPUTCONTROL)

    def _emulate_mouse(self, property_file=None):
        self.player.emulate(input_type='mouse', property_file=property_file)
        self.player.find_connected_inputs()

    def _playback(self, filepath, touch_type='touchpad'):
        """Playback a given input file on the given input."""
        self.player.playback(filepath, touch_type)

    def _blocking_playback(self, filepath, touch_type='touchpad'):
        """Playback a given input file on the given input; block until done."""
        self.player.blocking_playback(filepath, touch_type)

    def _set_touch_setting_by_inputcontrol(self, setting, value):
        """Set a given touch setting the given value by inputcontrol.

        @param setting: Name of touch setting, e.g. 'tapclick'.
        @param value: True for enabled, False for disabled.

        """
        cmd_value = 1 if value else 0
        utils.run('%s --%s %d' % (self._INPUTCONTROL, setting, cmd_value))
        logging.info('%s turned %s.', setting, 'on' if value else 'off')

    def _set_touch_setting(self, inputcontrol_setting, autotest_ext_setting,
                           value):
        """Set a given touch setting the given value.

        @param inputcontrol_setting: Name of touch setting for the inputcontrol
                                     script, e.g. 'tapclick'.
        @param autotest_ext_setting: Name of touch setting for the autotest
                                     extension, e.g. 'TapToClick'.
        @param value: True for enabled, False for disabled.

        """
        if self._has_inputcontrol:
          self._set_touch_setting_by_inputcontrol(inputcontrol_setting, value)
        elif self._autotest_ext is not None:
          self._autotest_ext.EvaluateJavaScript(
                  'chrome.autotestPrivate.set%s(%s);'
                  % (autotest_ext_setting, ("%s" % value).lower()))
        else:
          raise error.TestFail('Both inputcontrol and the autotest '
                               'extension are not availble.')

    def _set_australian_scrolling(self, value):
        """Set australian scrolling to the given value.

        @param value: True for enabled, False for disabled.

        """
        self._set_touch_setting('australian_scrolling', 'NaturalScroll', value)

    def _set_tap_to_click(self, value):
        """Set tap-to-click to the given value.

        @param value: True for enabled, False for disabled.

        """
        self._set_touch_setting('tapclick', 'TapToClick', value)

    def _set_tap_dragging(self, value):
        """Set tap dragging to the given value.

        @param value: True for enabled, False for disabled.

        """
        self._set_touch_setting('tapdrag', 'TapDragging', value)

    def _reload_page(self):
        """Reloads test page.  Presuposes self._tab.

        @raise: TestError if page is not reset.

        """
        self._tab.Navigate(self._tab.url)
        self._tab.WaitForDocumentReadyStateToBeComplete()

    def _set_autotest_ext(self, ext):
        """Set the autotest extension.

        @ext: the autotest extension object.

        """
        self._autotest_ext = ext

    def _set_default_scroll_position(self):
        """Set scroll position of page to default.  Presuposes self._tab."""
        self._tab.EvaluateJavaScript(
                'document.body.scrollTop=%s' % self._DEFAULT_SCROLL)

    def _get_scroll_position(self):
        """Return current scroll position of page.  Presuposes self._tab."""
        return int(self._tab.EvaluateJavaScript('document.body.scrollTop'))

    def _wait_for_default_scroll_position(self):
        """Wait for page to be at the default scroll position.

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
                exception=error.TestError('No scrolling occurred!'), timeout=30)

        # Wait until page has stopped moving.
        self._previous = self._DEFAULT_SCROLL
        def _movement_stopped():
            current = self._get_scroll_position()
            result = current == self._previous
            self._previous = current
            return result

        utils.poll_for_condition(
                lambda: _movement_stopped(), sleep_interval=1,
                exception=error.TestError('Page did not stop moving!'),
                timeout=30)

    def cleanup(self):
        self.player.close()
