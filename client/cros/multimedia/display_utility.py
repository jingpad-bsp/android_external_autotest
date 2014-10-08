# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utility to access the display-related functionality."""

import multiprocessing
import os
import re
import time
import telemetry

from autotest_lib.client.bin import utils
from autotest_lib.client.cros import constants, sys_power
from autotest_lib.client.cros.graphics import graphics_utils

TimeoutException = telemetry.core.util.TimeoutException


class DisplayUtility(object):
    """Utility to access the display-related functionality."""

    def __init__(self, chrome):
        self._chrome = chrome
        self._browser = chrome.browser


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

        tab = self._browser.tabs.New()
        try:
            tab.Navigate('chrome://settings-frame/display')
            tab.Activate()
            self._wait_for_display_options_to_appear(tab, display_index)
            return tab.EvaluateJavaScript(
                    "options.DisplayOptions.instance_"
                    "         .displays_[%(index)d].resolutions"
                    % {'index': display_index})
        finally:
            tab.Close()


    def set_resolution(self, display_index, width, height, timeout=3):
        """Sets the resolution of the specified display.

        @param display_index: index of the display to set resolution for.
        @param width: width of the resolution
        @param height: height of the resolution
        @param timeout: maximal time in seconds waiting for the new resolution
                to settle in.
        @raise TimeoutException when the operation is timed out.
        """

        tab = self._browser.tabs.New()
        try:
            tab.Navigate('chrome://settings-frame/display')
            tab.Activate()
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
                    var is_m38 = modes.length > 0
                             && "originalWidth" in modes[0];
                    if (is_m38) {
                      for (index in modes) {
                          var mode = modes[index];
                          if (mode.originalWidth == %(width)d &&
                                  mode.originalHeight == %(height)d) {
                              chrome.send('setDisplayMode', [display.id, mode]);
                              break;
                          }
                      }
                    } else {
                      chrome.send('setResolution',
                          [display.id, %(width)d, %(height)d]);
                    }
                    """
                    % {'index': display_index, 'width': width, 'height': height}
            )

            # TODO(tingyuan):
            # Support for multiple external monitors (i.e. for chromebox)

            end_time = time.time() + timeout
            while time.time() < end_time:
                r = self.get_resolution(self.get_external_connector_name())
                if (width, height) == (r[0], r[1]):
                    return True
                time.sleep(0.1)
            raise TimeoutException("Failed to change resolution to %r (%r"
                    " detected)" % ((width, height), r))
        finally:
            tab.Close()


    def get_resolution(self, output):
        """Gets the resolution of the specified output.

        @param output: The output name as a string.

        @return The resolution of output as a tuple (width, height,
            fb_offset_x, fb_offset_y) of ints.
        """

        regexp = re.compile(
                r'^([-A-Za-z0-9]+)\s+connected\s+(\d+)x(\d+)\+(\d+)\+(\d+)',
                re.M)
        match = regexp.findall(utils.call_xrandr())
        for m in match:
            if m[0] == output:
                return (int(m[1]), int(m[2]), int(m[3]), int(m[4]))
        return (0, 0, 0, 0)


    def take_tab_screenshot(self, url_pattern, output_suffix):
        """Takes a screenshot of the tab specified by the given url pattern.

        The captured screenshot is saved to:
            /tmp/screenshot_<output_suffix>_<last_part_of_url>.png

        @param url_pattern: A string of url pattern used to search for tabs.
        @param output_suffix: A suffix appended to the file name of captured
                PNG image.
        """
        if not url_pattern:
            # If no URL pattern is provided, defaults to capture all the tabs
            # that show PNG images.
            url_pattern = '.png'

        tabs = self._browser.tabs
        screenshots = []
        for i in xrange(0, len(tabs)):
            if url_pattern in tabs[i].url:
                screenshots.append((tabs[i].url, tabs[i].Screenshot(timeout=5)))

        output_file = ('/tmp/screenshot_%s_%%s.png' % output_suffix)
        for url, screenshot in screenshots:
            image_filename = os.path.splitext(url.rsplit('/', 1)[-1])[0]
            screenshot.WriteFile(output_file % image_filename)
        return True


    def toggle_mirrored(self):
        """Toggles mirrored.

        Emulates L_Ctrl + Maximize in X server to toggle mirrored.
        """
        graphics_utils.press_key('ctrl+F4')
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


    def get_external_connector_name(self):
        """Gets the name of the external output connector.

        @return The external output connector name as a string, if any.
                Otherwise, return False.
        """
        xrandr_output = utils.get_xrandr_output_state()
        for output in xrandr_output.iterkeys():
            if (output.startswith('HDMI') or
                output.startswith('DP') or
                output.startswith('DVI')):
                return output
        return False


    def get_internal_connector_name(self):
        """Gets the name of the internal output connector.

        @return The internal output connector name as a string, if any.
                Otherwise, return False.
        """
        xrandr_output = utils.get_xrandr_output_state()
        for output in xrandr_output.iterkeys():
            # reference: chromium_org/chromeos/display/output_util.cc
            if (output.startswith('eDP') or
                output.startswith('LVDS') or
                output.startswith('DSI')):
                return output
        return False


    def wait_output_connected(self, output):
        """Wait for output to connect.

        @param output: The output name as a string.

        @return: True if output is connected; False otherwise.
        """
        def _is_connected(output):
            xrandr_output = utils.get_xrandr_output_state()
            if output not in xrandr_output:
                return False
            return xrandr_output[output]
        return utils.wait_for_value(lambda: _is_connected(output),
                                    expected_value=True)


    def load_url(self, url):
        """Loads the given url in a new tab.

        @param url: The url to load as a string.
        """
        tab = self._browser.tabs.New()
        tab.Navigate(url)
        tab.Activate()
        return True


    def close_tab(self, index=-1):
        """Closes the tab of the given index.

        @param index: The tab index to close. Defaults to the last tab.
        """
        self._browser.tabs[index].Close()
        return True
