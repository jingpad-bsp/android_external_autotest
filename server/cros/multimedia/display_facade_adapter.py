# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""An adapter to remotely access the display facade on DUT."""

import logging
import os
import tempfile
import xmlrpclib

from PIL import Image

from autotest_lib.client.cros.multimedia.display_info import DisplayInfo


class DisplayFacadeRemoteAdapter(object):
    """DisplayFacadeRemoteAdapter is an adapter to remotely control DUT display.

    The Autotest host object representing the remote DUT, passed to this
    class on initialization, can be accessed from its _client property.

    """
    def __init__(self, host, remote_facade_proxy):
        """Construct a DisplayFacadeRemoteAdapter.

        @param host: Host object representing a remote host.
        @param remote_facade_proxy: RemoteFacadeProxy object.
        """
        self._client = host
        self._proxy = remote_facade_proxy


    @property
    def _display_proxy(self):
        """Gets the proxy to DUT display facade.

        @return XML RPC proxy to DUT display facade.
        """
        return self._proxy.display


    def get_external_connector_name(self):
        """Gets the name of the external output connector.

        @return The external output connector name as a string; False if nothing
                is connected.
        """
        return self._display_proxy.get_external_connector_name()


    def get_internal_connector_name(self):
        """Gets the name of the internal output connector.

        @return The internal output connector name as a string; False if nothing
                is connected.
        """
        return self._display_proxy.get_internal_connector_name()


    def load_calibration_image(self, resolution):
        """Load a full screen calibration image from the HTTP server.

        @param resolution: A tuple (width, height) of resolution.
        """
        self._display_proxy.load_calibration_image(resolution)


    def close_tab(self, index=-1):
        """Closes the tab of the given index.

        @param index: The tab index to close. Defaults to the last tab.
        """
        self._display_proxy.close_tab(index)


    def is_mirrored_enabled(self):
        """Checks the mirrored state.

        @return True if mirrored mode is enabled.
        """
        return self._display_proxy.is_mirrored_enabled()


    def set_mirrored(self, is_mirrored):
        """Sets mirrored mode.

        @param is_mirrored: True or False to indicate mirrored state.
        """
        return self._display_proxy.set_mirrored(is_mirrored)


    def is_display_primary(self, internal=True):
        """Checks if internal screen is primary display.

        @param internal: is internal/external screen primary status requested
        @return boolean True if internal display is primary.
        """
        return self._display_proxy.is_display_primary(internal)


    def suspend_resume(self, suspend_time=10):
        """Suspends the DUT for a given time in second.

        @param suspend_time: Suspend time in second, default: 10s.
        """
        try:
            self._display_proxy.suspend_resume(suspend_time)
        except xmlrpclib.Fault as e:
            # Log suspend/resume errors but continue the test.
            logging.error('suspend_resume error: %s', str(e))


    def suspend_resume_bg(self, suspend_time=10):
        """Suspends the DUT for a given time in second in the background.

        @param suspend_time: Suspend time in second, default: 10s.
        """
        # TODO(waihong): Use other general API instead of this RPC.
        self._display_proxy.suspend_resume_bg(suspend_time)


    def wait_external_display_connected(self, display):
        """Waits for the specified display to be connected.

        @param display: The display name as a string, like 'HDMI1', or
                        False if no external display is expected.
        @return: True if display is connected; False otherwise.
        """
        return self._display_proxy.wait_external_display_connected(display)


    def hide_cursor(self):
        """Hides mouse cursor by sending a keystroke."""
        self._display_proxy.hide_cursor()


    def set_content_protection(self, state):
        """Sets the content protection of the external screen.

        @param state: One of the states 'Undesired', 'Desired', or 'Enabled'
        """
        self._display_proxy.set_content_protection(state)


    def get_content_protection(self):
        """Gets the state of the content protection.

        @param output: The output name as a string.
        @return: A string of the state, like 'Undesired', 'Desired', or 'Enabled'.
                 False if not supported.
        """
        return self._display_proxy.get_content_protection()


    def _take_screenshot(self, screenshot_func):
        """Gets screenshot from DUT.

        @param screenshot_func: function to take a screenshot and save the image
                to specified path on DUT. Usage: screenshot_func(remote_path).

        @return: An Image object, or None if any error.
        """
        with tempfile.NamedTemporaryFile(suffix='.png') as f:
            basename = os.path.basename(f.name)
            remote_path = os.path.join('/tmp', basename)
            screenshot_func(remote_path)
            self._client.get_file(remote_path, f.name)
            return Image.open(f.name)


    def capture_internal_screen(self):
        """Captures the internal screen framebuffer.

        @return: An Image object. None if any error.
        """
        screenshot_func = self._display_proxy.take_internal_screenshot
        return self._take_screenshot(screenshot_func)


    # TODO(ihf): This needs to be fixed for multiple external screens.
    def capture_external_screen(self):
        """Captures the external screen framebuffer.

        @return: An Image object.
        """
        screenshot_func = self._display_proxy.take_external_screenshot
        return self._take_screenshot(screenshot_func)


    def get_external_resolution(self):
        """Gets the resolution of the external screen.

        @return The resolution tuple (width, height)
        """
        return tuple(self._display_proxy.get_external_resolution())


    def get_internal_resolution(self):
        """Gets the resolution of the internal screen.

        @return The resolution tuple (width, height)
        """
        return tuple(self._display_proxy.get_internal_resolution())


    def set_resolution(self, display_index, width, height):
        """Sets the resolution on the specified display.

        @param display_index: index of the display to set resolutions for.
        @param width: width of the resolution
        @param height: height of the resolution
        """
        self._display_proxy.set_resolution(display_index, width, height)


    # pylint: disable = W0141
    def get_display_info(self):
        """Gets the information of all the displays that are connected to the
                DUT.

        @return: list of object DisplayInfo for display informtion
        """
        return map(DisplayInfo, self._display_proxy.get_display_info())


    def get_display_modes(self, display_index):
        """Gets the display modes of the specified display.

        @param display_index: index of the display to get modes from; the index
            is from the DisplayInfo list obtained by get_display_info().

        @return: list of DisplayMode dicts.
        """
        return self._display_proxy.get_display_modes(display_index)


    def get_available_resolutions(self, display_index):
        """Gets the resolutions from the specified display.

        @return a list of (width, height) tuples.
        """
        return [tuple(r) for r in
                self._display_proxy.get_available_resolutions(display_index)]


    def get_first_external_display_index(self):
        """Gets the first external display index.

        @return the index of the first external display; False if not found.
        """
        return self._display_proxy.get_first_external_display_index()
