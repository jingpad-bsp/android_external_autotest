# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class FrameSender(object):
    """Context manager for sending management frames."""

    def __init__(self, router, frame_type, channel, ssid_prefix=None,
                 num_bss=None, frame_count=None, delay=None):
        """
        @param router: LinuxRouter object router to send frames from.
        @param frame_type: int management frame type.
        @param channel: int targeted channel.
        @param ssid_prefix: string SSID prefix for BSSes in the frames.
        @param num_bss: int number of BSSes configured for sending frames.
        @param frame_count: int number of frames to send, frame_count of 0
                implies infinite number of frames.
        @param delay: int delay in between frames in milliseconds.
        """
        self._router = router
        self._channel = channel
        self._frame_type = frame_type
        self._ssid_prefix = ssid_prefix
        self._num_bss = num_bss
        self._frame_count = frame_count
        self._delay = delay
        self._interface = None
        self._pid = None

    def __enter__(self):
        self._interface = self._router.setup_management_frame_interface(
                self._channel)
        self._pid = self._router.send_management_frame(self._interface,
                self._frame_type, self._channel, ssid_prefix=self._ssid_prefix,
                num_bss=self._num_bss, frame_count=self._frame_count,
                delay=self._delay)
        return self


    def __exit__(self, exception, value, traceback):
        if self._interface:
            self._router.release_interface(self._interface)
        if self._pid:
            self._router.host.run('kill %d' % self._pid, ignore_status=True)

