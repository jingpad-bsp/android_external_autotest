# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""An adapter to access the local display facade."""

import logging
import tempfile
from PIL import Image

from autotest_lib.client.cros import sys_power
from autotest_lib.client.cros.multimedia import display_facade_native
from autotest_lib.client.cros.multimedia.display_info import DisplayInfo


class DisplayFacadeLocalAdapter(object):
    """DisplayFacadeLocalAdapter is an adapter to control the local display.

    Methods with non-native-type arguments go to this class and do some
    conversion; otherwise, go to the DisplayFacadeNative class.
    """

    def __init__(self, chrome):
        """Construct a DisplayFacadeLocalAdapter.

        @param chrome: A Chrome object.
        """
        # Create a DisplayFacadeNative object as a component such that this
        # class can expose and manipulate its interfaces.
        self._display_component = display_facade_native.DisplayFacadeNative(
                chrome)


    def get_external_connector_name(self):
        """Gets the name of the external output connector.

        @return The external output connector name as a string; False if nothing
                is connected.
        """
        return self._display_component.get_external_connector_name()


    def get_internal_connector_name(self):
        """Gets the name of the internal output connector.

        @return The internal output connector name as a string; False if nothing
                is connected.
        """
        return self._display_component.get_internal_connector_name()


    def load_calibration_image(self, resolution):
        """Load a full screen calibration image from the HTTP server.

        @param resolution: A tuple (width, height) of resolution.
        """
        self._display_component.load_calibration_image(resolution)


    def close_tab(self, index=-1):
        """Closes the tab of the given index.

        @param index: The tab index to close. Defaults to the last tab.
        """
        self._display_component.close_tab(index)


    def is_mirrored_enabled(self):
        """Checks the mirrored state.

        @return True if mirrored mode is enabled.
        """
        return self._display_component.is_mirrored_enabled()


    def set_mirrored(self, is_mirrored):
        """Sets mirrored mode.

        @param is_mirrored: True or False to indicate mirrored state.
        """
        return self._display_component.set_mirrored(is_mirrored)


    def is_display_primary(self, internal=True):
        """Checks if internal screen is primary display.

        @param internal: is internal/external screen primary status requested
        @return boolean True if internal display is primary.
        """
        return self._display_component.is_display_primary(internal)


    def suspend_resume(self, suspend_time=10):
        """Suspends the DUT for a given time in second.

        @param suspend_time: Suspend time in second.
        """
        try:
            self._display_component.suspend_resume(suspend_time)
        except sys_power.SpuriousWakeupError as e:
            # Log suspend/resume errors but continue the test.
            logging.error('suspend_resume error: %s', str(e))


    def suspend_resume_bg(self, suspend_time=10):
        """Suspends the DUT for a given time in second in the background.

        @param suspend_time: Suspend time in second, default: 10s.
        """
        self._display_component.suspend_resume_bg(suspend_time)


    def wait_external_display_connected(self, display):
        """Waits for the specified display to be connected.

        @param display: The display name as a string, like 'HDMI1', or
                        False if no external display is expected.
        @return: True if display is connected; False otherwise.
        """
        return self._display_component.wait_external_display_connected(display)


    def hide_cursor(self):
        """Hides mouse cursor by sending a keystroke."""
        self._display_component.hide_cursor()


    def set_content_protection(self, state):
        """Sets the content protection of the external screen.

        @param state: One of the states 'Undesired', 'Desired', or 'Enabled'
        """
        self._display_component.set_content_protection(state)


    def get_content_protection(self):
        """Gets the state of the content protection.

        @param output: The output name as a string.
        @return: A string of the state, like 'Undesired', 'Desired', or 'Enabled'.
                 False if not supported.
        """
        return self._display_component.get_content_protection()


    def _read_root_window_rect(self, id):
        """Reads the given rectangle from frame buffer.

        @param crtc: The id of the crtc to read.

        @return: An Image object, or None if any error.
        """
        if 0 in (w, h):
            # Not a valid rectangle
            return None

        with tempfile.NamedTemporaryFile(suffix='.png') as f:
            self._display_component.take_screenshot_crtc(f.name, crtc_id=id)
            return Image.open(f.name)


    def capture_internal_screen(self):
        """Captures the internal screen framebuffer.

        @return: An Image object. None if any error.
        """
        id = self._display_component.get_internal_crtc()
        return self._read_root_window_rect(id)


    # TODO(ihf): This function needs to be fixed for multiple screens.
    def capture_external_screen(self):
        """Captures the external screen framebuffer.

        @return: An Image object.
        """
        id = self._display_component.get_external_crtc()
        return self._read_root_window_rect(id)


    def get_external_resolution(self):
        """Gets the resolution of the external screen.

        @return The resolution tuple (width, height) or None if no external
                display is connected.
        """
        resolution = self._display_component.get_external_resolution()
        return tuple(resolution) if resolution else None


    def get_internal_resolution(self):
        """Gets the resolution of the internal screen.

        @return The resolution tuple (width, height)
        """
        return tuple(self._display_component.get_internal_resolution())


    def set_resolution(self, display_index, width, height):
        """Sets the resolution on the specified display.

        @param display_index: index of the display to set resolutions for.
        @param width: width of the resolution
        @param height: height of the resolution
        """
        self._display_component.set_resolution(display_index, width, height)


    def get_display_info(self):
        """Gets the information of all the displays that are connected to the
                DUT.

        @return: list of object DisplayInfo for display informtion
        """
        return map(DisplayInfo, self._display_component.get_display_info())


    def get_display_modes(self, display_index):
        """Gets the display modes of the specified display.

        @param display_index: index of the display to get modes from; the index
            is from the DisplayInfo list obtained by get_display_info().

        @return: list of DisplayMode dicts.
        """
        return self._display_component.get_display_modes(display_index)


    def get_available_resolutions(self, display_index):
        """Gets the resolutions from the specified display.

        @return a list of (width, height) tuples.
        """
        return [tuple(r) for r in
                self._display_component.get_available_resolutions(
                    display_index)]


    def get_first_external_display_index(self):
        """Gets the first external display index.

        @return the index of the first external display; False if not found.
        """
        return self._display_component.get_first_external_display_index()
