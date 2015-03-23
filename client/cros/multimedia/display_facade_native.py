# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Facade to access the display-related functionality."""

import exceptions
import multiprocessing
import numpy
import os
import re
import time
import telemetry
import logging
import pprint
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome, retry
from autotest_lib.client.cros import constants, sys_power
from autotest_lib.client.cros.graphics import graphics_utils
from autotest_lib.client.cros.multimedia import image_generator

class TimeoutException(Exception):
    pass


_FLAKY_CALL_RETRY_TIMEOUT_SEC = 60
_FLAKY_CHROME_CALL_RETRY_DELAY_SEC = 1
_FLAKY_DISPLAY_CALL_RETRY_DELAY_SEC = 2

_retry_chrome_call = retry.retry(
        (chrome.Error, exceptions.IndexError),
        timeout_min=_FLAKY_CALL_RETRY_TIMEOUT_SEC / 60.0,
        delay_sec=_FLAKY_CHROME_CALL_RETRY_DELAY_SEC)

_retry_display_call = retry.retry(
        (KeyError, error.CmdError),
        timeout_min=_FLAKY_CALL_RETRY_TIMEOUT_SEC / 60.0,
        delay_sec=_FLAKY_DISPLAY_CALL_RETRY_DELAY_SEC)


class DisplayFacadeNative(object):
    """Facade to access the display-related functionality.

    The methods inside this class only accept Python native types.
    """

    CALIBRATION_IMAGE_PATH = '/tmp/calibration.svg'

    def __init__(self, chrome):
        self._chrome = chrome
        self._browser = chrome.browser
        self._image_generator = image_generator.ImageGenerator()


    @_retry_chrome_call
    def get_display_info(self):
        """Gets the display info from Chrome.system.display API.

        @return array of dict for display info.
        """

        extension = self._chrome.get_extension(
                constants.MULTIMEDIA_TEST_EXTENSION)
        if not extension:
            raise RuntimeError('Graphics test extension not found')
        extension.ExecuteJavaScript('window.__display_info = null;')
        extension.ExecuteJavaScript(
                "chrome.system.display.getInfo(function(info) {"
                "window.__display_info = info;})")
        utils.wait_for_value(lambda: (
                extension.EvaluateJavaScript("window.__display_info") != None),
                expected_value=True)
        return extension.EvaluateJavaScript("window.__display_info")


    def _wait_for_display_options_to_appear(self, tab, display_index,
                                            timeout=16):
        """Waits for option.DisplayOptions to appear.

        The function waits until options.DisplayOptions appears or is timed out
                after the specified time.

        @param tab: the tab where the display options dialog is shown.
        @param display_index: index of the display.
        @param timeout: time wait for display options appear.

        @raise RuntimeError when display_index is out of range
        @raise TimeoutException when the operation is timed out.
        """

        tab.WaitForJavaScriptExpression(
                    "typeof options !== 'undefined' &&"
                    "typeof options.DisplayOptions !== 'undefined' &&"
                    "typeof options.DisplayOptions.instance_ !== 'undefined' &&"
                    "typeof options.DisplayOptions.instance_"
                    "       .displays_ !== 'undefined'", timeout)

        if not tab.EvaluateJavaScript(
                    "options.DisplayOptions.instance_.displays_.length > %d"
                    % (display_index)):
            raise RuntimeError('Display index out of range: '
                    + str(tab.EvaluateJavaScript(
                    "options.DisplayOptions.instance_.displays_.length")))

        tab.WaitForJavaScriptExpression(
                "typeof options.DisplayOptions.instance_"
                "         .displays_[%(index)d] !== 'undefined' &&"
                "typeof options.DisplayOptions.instance_"
                "         .displays_[%(index)d].id !== 'undefined' &&"
                "typeof options.DisplayOptions.instance_"
                "         .displays_[%(index)d].resolutions !== 'undefined'"
                % {'index': display_index}, timeout)


    def get_display_modes(self, display_index):
        """Gets all the display modes for the specified display.

        The modes are obtained from chrome://settings-frame/display via
        telemetry.

        @param display_index: index of the display to get modes from.

        @return: A list of DisplayMode dicts.

        @raise TimeoutException when the operation is timed out.
        """
        try:
            tab = self._load_url('chrome://settings-frame/display')
            self._wait_for_display_options_to_appear(tab, display_index)
            return tab.EvaluateJavaScript(
                    "options.DisplayOptions.instance_"
                    "         .displays_[%(index)d].resolutions"
                    % {'index': display_index})
        finally:
            self.close_tab()


    def get_available_resolutions(self, display_index):
        """Gets the resolutions from the specified display.

        @return a list of (width, height) tuples.
        """
        # Start from M38 (refer to http://codereview.chromium.org/417113012),
        # a DisplayMode dict contains 'originalWidth'/'originalHeight'
        # in addition to 'width'/'height'.
        # OriginalWidth/originalHeight is what is supported by the display
        # while width/height is what is shown to users in the display setting.
        modes = self.get_display_modes(display_index)
        if modes:
            if 'originalWidth' in modes[0]:
                # M38 or newer
                # TODO(tingyuan): fix loading image for cases where original
                #                 width/height is different from width/height.
                return list(set([(mode['originalWidth'], mode['originalHeight'])
                        for mode in modes]))

        # pre-M38
        return [(mode['width'], mode['height']) for mode in modes
                if 'scale' not in mode]


    def get_first_external_display_index(self):
        """Gets the first external display index.

        @return the index of the first external display; False if not found.
        """
        # Get the first external and enabled display
        for index, display in enumerate(self.get_display_info()):
            if display['isEnabled'] and not display['isInternal']:
                return index
        return False


    def set_resolution(self, display_index, width, height, timeout=3):
        """Sets the resolution of the specified display.

        @param display_index: index of the display to set resolution for.
        @param width: width of the resolution
        @param height: height of the resolution
        @param timeout: maximal time in seconds waiting for the new resolution
                to settle in.
        @raise TimeoutException when the operation is timed out.
        """

        try:
            tab = self._load_url('chrome://settings-frame/display')
            self._wait_for_display_options_to_appear(tab, display_index)

            tab.ExecuteJavaScript(
                    # Start from M38 (refer to CR:417113012), a DisplayMode dict
                    # contains 'originalWidth'/'originalHeight' in addition to
                    # 'width'/'height'. OriginalWidth/originalHeight is what is
                    # supported by the display while width/height is what is
                    # shown to users in the display setting.
                    """
                    var display = options.DisplayOptions.instance_
                              .displays_[%(index)d];
                    var modes = display.resolutions;
                    for (index in modes) {
                        var mode = modes[index];
                        if (mode.originalWidth == %(width)d &&
                                mode.originalHeight == %(height)d) {
                            chrome.send('setDisplayMode', [display.id, mode]);
                            break;
                        }
                    }
                    """
                    % {'index': display_index, 'width': width, 'height': height}
            )

            def _get_selected_resolution():
                modes = tab.EvaluateJavaScript(
                        """
                        options.DisplayOptions.instance_
                                 .displays_[%(index)d].resolutions
                        """
                        % {'index': display_index})
                for mode in modes:
                    if mode['selected']:
                        return (mode['originalWidth'], mode['originalHeight'])

            # TODO(tingyuan):
            # Support for multiple external monitors (i.e. for chromebox)
            end_time = time.time() + timeout
            while time.time() < end_time:
                r = _get_selected_resolution()
                if (width, height) == (r[0], r[1]):
                    return True
                time.sleep(0.1)
            raise TimeoutException('Failed to change resolution to %r (%r'
                                   ' detected)' % ((width, height), r))
        finally:
            self.close_tab()

    @_retry_display_call
    def get_external_resolution(self):
        """Gets the resolution of the external screen.

        @return The resolution tuple (width, height)
        """
        return graphics_utils.get_external_resolution()

    def get_internal_resolution(self):
        """Gets the resolution of the internal screen.

        @return The resolution tuple (width, height) or None if internal screen
                is not available
        """
        for display in self.get_display_info():
            if display['isInternal']:
                bounds = display['bounds']
                return (bounds['width'], bounds['height'])
        return None


    def set_content_protection(self, state):
        """Sets the content protection of the external screen.

        @param state: One of the states 'Undesired', 'Desired', or 'Enabled'
        """
        connector = self.get_external_connector_name()
        graphics_utils.set_content_protection(connector, state)


    def get_content_protection(self):
        """Gets the state of the content protection.

        @param output: The output name as a string.
        @return: A string of the state, like 'Undesired', 'Desired', or 'Enabled'.
                 False if not supported.
        """
        connector = self.get_external_connector_name()
        return graphics_utils.get_content_protection(connector)


    def get_external_crtc(self):
        """Gets the external crtc.

        @return The id of the external crtc."""
        return graphics_utils.get_external_crtc()


    def get_internal_crtc(self):
        """Gets the internal crtc.

        @retrun The id of the internal crtc."""
        return graphics_utils.get_internal_crtc()


    def get_output_rect(self, output):
        """Gets the size and position of the given output on the screen buffer.

        @param output: The output name as a string.

        @return A tuple of the rectangle (width, height, fb_offset_x,
                fb_offset_y) of ints.
        """
        regexp = re.compile(
                r'^([-A-Za-z0-9]+)\s+connected\s+(\d+)x(\d+)\+(\d+)\+(\d+)',
                re.M)
        match = regexp.findall(graphics_utils.call_xrandr())
        for m in match:
            if m[0] == output:
                return (int(m[1]), int(m[2]), int(m[3]), int(m[4]))
        return (0, 0, 0, 0)


    def take_internal_screenshot(self, path):
        if utils.is_freon():
            self.take_screenshot_crtc(path, self.get_internal_crtc())
        else:
            output = self.get_internal_connector_name()
            box = self.get_output_rect(output)
            graphics_utils.take_screenshot_crop_x(path, box)
            return output, box  # for logging/debugging


    def take_external_screenshot(self, path):
        if utils.is_freon():
            self.take_screenshot_crtc(path, self.get_external_crtc())
        else:
            output = self.get_external_connector_name()
            box = self.get_output_rect(output)
            graphics_utils.take_screenshot_crop_x(path, box)
            return output, box  # for logging/debugging


    def take_screenshot_crtc(self, path, id):
        """Captures the DUT screenshot, use id for selecting screen.

        @param path: path to image file.
        @param id: The id of the crtc to screenshot.
        """

        graphics_utils.take_screenshot_crop(path, crtc_id=id)
        return True


    def take_tab_screenshot(self, output_path, url_pattern=None):
        """Takes a screenshot of the tab specified by the given url pattern.

        @param output_path: A path of the output file.
        @param url_pattern: A string of url pattern used to search for tabs.
                            Default is to look for .svg image.
        """
        if url_pattern is None:
            # If no URL pattern is provided, defaults to capture the first
            # tab that shows SVG image.
            url_pattern = '.svg'

        tabs = self._browser.tabs
        for i in xrange(0, len(tabs)):
            if url_pattern in tabs[i].url:
                data = tabs[i].Screenshot(timeout=5)
                # Flip the colors from BGR to RGB.
                data = numpy.fliplr(data.reshape(-1, 3)).reshape(data.shape)
                data.tofile(output_path)
                break
        return True


    def toggle_mirrored(self):
        """Toggles mirrored."""
        graphics_utils.screen_toggle_mirrored()
        return True


    def hide_cursor(self):
        """Hides mouse cursor."""
        graphics_utils.hide_cursor()
        return True


    def is_mirrored_enabled(self):
        """Checks the mirrored state.

        @return True if mirrored mode is enabled.
        """
        return bool(self.get_display_info()[0]['mirroringSourceId'])


    def set_mirrored(self, is_mirrored):
        """Sets mirrored mode.

        @param is_mirrored: True or False to indicate mirrored state.
        """
        retries = 3
        while self.is_mirrored_enabled() != is_mirrored and retries > 0:
            self.toggle_mirrored()
            time.sleep(3)
            retries -= 1
        return self.is_mirrored_enabled() == is_mirrored


    def is_display_primary(self, internal=True):
        """Checks if internal screen is primary display.

        @param internal: is internal/external screen primary status requested
        @return boolean True if internal display is primary.
        """
        for info in self.get_display_info():
            if info['isInternal'] == internal and info['isPrimary']:
                return True
        return False


    def suspend_resume(self, suspend_time=10):
        """Suspends the DUT for a given time in second.

        @param suspend_time: Suspend time in second.
        """
        sys_power.do_suspend(suspend_time)
        return True


    def suspend_resume_bg(self, suspend_time=10):
        """Suspends the DUT for a given time in second in the background.

        @param suspend_time: Suspend time in second.
        """
        process = multiprocessing.Process(target=self.suspend_resume,
                                          args=(suspend_time,))
        process.start()
        return True


    @_retry_display_call
    def get_external_connector_name(self):
        """Gets the name of the external output connector.

        @return The external output connector name as a string, if any.
                Otherwise, return False.
        """
        return graphics_utils.get_external_connector_name()


    def get_internal_connector_name(self):
        """Gets the name of the internal output connector.

        @return The internal output connector name as a string, if any.
                Otherwise, return False.
        """
        return graphics_utils.get_internal_connector_name()


    def wait_external_display_connected(self, display):
        """Waits for the specified external display to be connected.

        @param display: The display name as a string, like 'HDMI1', or
                        False if no external display is expected.
        @return: True if display is connected; False otherwise.
        """
        result = utils.wait_for_value(self.get_external_connector_name,
                                      expected_value=display)
        return result == display


    @_retry_chrome_call
    def _load_url(self, url):
        """Loads the given url in a new tab.

        @param url: The url to load as a string.
        @return: A new tab object.
        """
        tab = self._browser.tabs.New()
        tab.Navigate(url)
        tab.Activate()
        return tab


    def load_calibration_image(self, resolution):
        """Load a full screen calibration image from the HTTP server.

        @param resolution: A tuple (width, height) of resolution.
        """
        path = self.CALIBRATION_IMAGE_PATH
        self._image_generator.generate_image(resolution[0], resolution[1], path)
        os.chmod(path, 0644)
        self._load_url('file://%s' % path)
        return True


    @_retry_chrome_call
    def close_tab(self, index=-1):
        """Closes the tab of the given index.

        @param index: The tab index to close. Defaults to the last tab.
        """
        self._browser.tabs[index].Close()
        return True
