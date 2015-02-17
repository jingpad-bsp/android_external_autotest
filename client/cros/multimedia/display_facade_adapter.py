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


class DisplayFacadeLocalAdapter(display_facade_native.DisplayFacadeNative):
    """DisplayFacadeLocalAdapter is an adapter to control the local display.

    Methods with non-native-type arguments go to this class and do some
    conversion; otherwise, go to the DisplayFacadeNative class.
    """

    @property
    def _display_native(self):
        """Gets its super class, the native display facade.

        @return the native display facade.
        """
        return super(DisplayFacadeLocalAdapter, self)


    def _read_root_window_rect(self, id):
        """Reads the given rectangle from frame buffer.

        @param crtc: The id of the crtc to read.

        @return: An Image object, or None if any error.
        """
        if 0 in (w, h):
            # Not a valid rectangle
            return None

        with tempfile.NamedTemporaryFile(suffix='.png') as f:
            self._display_native.take_screenshot_crtc(f.name, crtc_id=id)
            return Image.open(f.name)


    def capture_internal_screen(self):
        """Captures the internal screen framebuffer.

        @return: An Image object. None if any error.
        """
        id = self._display_native.get_internal_crtc()
        return self._read_root_window_rect(id)


    # TODO(ihf): This function needs to be fixed for multiple screens.
    def capture_external_screen(self):
        """Captures the external screen framebuffer.

        @return: An Image object.
        """
        id = self._display_native.get_external_crtc()
        return self._read_root_window_rect(id)


    def get_display_info(self):
        """Gets the information of all the displays that are connected to the
                DUT.

        @return: list of object DisplayInfo for display informtion
        """
        return map(DisplayInfo, self._display_native.get_display_info())


    def suspend_resume(self, suspend_time=10):
        """Suspends the DUT for a given time in second.

        @param suspend_time: Suspend time in second.
        """
        try:
            self._display_native.suspend_resume(suspend_time)
        except sys_power.SpuriousWakeupError as e:
            # Log suspend/resume errors but continue the test.
            logging.error('suspend_resume error: %s', str(e))
