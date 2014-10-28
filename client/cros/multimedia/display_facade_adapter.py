# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""An adapter to access the local display facade."""

import tempfile
from PIL import Image

from autotest_lib.client.cros.multimedia import display_facade_native
from autotest_lib.client.cros.multimedia.display_helper import DisplayInfo


class DisplayFacadeLocalAdapter(display_facade_native.DisplayFacadeNative):
    """DisplayFacadeLocalAdapter is an adapter to control the local display.

    Methods with non-native-type arguments go to this class and do some
    conversion; otherwise, go to the DisplayFacadeNative class.
    """

    def _read_root_window_rect(self, w, h, x, y):
        """Reads the given rectangle from frame buffer.

        @param w: The width of the rectangle to read.
        @param h: The height of the rectangle to read.
        @param x: The x coordinate.
        @param y: The y coordinate.

        @return: An Image object, or None if any error.
        """
        if 0 in (w, h):
            # Not a valid rectangle
            return None

        with tempfile.NamedTemporaryFile(suffix='.rgb') as f:
            box = (x, y, x + w, y + h)
            self._display_proxy.take_screenshot_crop(f.name, box)
            return Image.fromstring('RGB', (w, h), open(f.name).read())


    def capture_internal_screen(self):
        """Captures the internal screen framebuffer.

        @return: An Image object. None if any error.
        """
        output = self.get_internal_connector_name()
        return self._read_root_window_rect(*self.get_output_rect(output))


    def capture_external_screen(self):
        """Captures the external screen framebuffer.

        @return: An Image object.
        """
        output = self.get_external_connector_name()
        return self._read_root_window_rect(*self.get_output_rect(output))


    def get_display_info(self):
        """Gets the information of all the displays that are connected to the
                DUT.

        @return: list of object DisplayInfo for display informtion
        """
        return map(DisplayInfo, self._display_proxy.get_display_info())
