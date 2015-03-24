# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error


class ChameleonVideoCapturer(object):
    """
    Wraps around chameleon APIs to provide an easy way to capture video frames.

    """


    def __init__(self, chameleon_port, display_facade, dest_dir,
                 image_format, timeout_input_stable_s=10,
                 timeout_get_all_frames_s=60,
                 box=None):

        self.chameleon_port = chameleon_port
        self.display_facade = display_facade
        self.dest_dir = dest_dir
        self.image_format = image_format
        self.timeout_input_stable_s = timeout_input_stable_s
        self.timeout_get_all_frames_s = timeout_get_all_frames_s
        self.box = box

        self.was_plugged = None


    def __enter__(self):
        self.was_plugged = self.chameleon_port.plugged

        if not self.was_plugged:
            self.chameleon_port.plug()
            self.chameleon_port.wait_video_input_stable(
                   self.timeout_input_stable_s)

        self.display_facade.set_mirrored(True)

        return self


    def capture(self, player, max_frame_count, box=None):
        """
        Asynchronously begins capturing video frames. Stops capturing when the
        number of frames captured is equal or more than max_frame_count.

        @param player: VimeoPlayer or NativeHTML5Player.
        @param max_frame_count: int, the maximum number of frames we want.
        @param box: int tuple, left, upper, right, lower pixel coordinates.
                    Defines the rectangular boundary within which to compare.
        @return: list of paths to images captured.

        """

        if not box:
            box = self.box

        self.chameleon_port.start_capturing_video(box)

        player.play()

        error_msg = "Couldn't get the right number of frames"

        utils.poll_for_condition(
                lambda: self.chameleon_port.get_captured_frame_count() >=
                max_frame_count,
                error.TestError(error_msg),
                self.timeout_get_all_frames_s)

        self.chameleon_port.stop_capturing_video()

        first_index = 0
        count = self.chameleon_port.get_captured_frame_count()

        checksums = self.chameleon_port.get_captured_checksums(0, count)

        for i in xrange(1, count):
            if checksums[0] != checksums[i]:
                first_index = i
                break

        test_images = []
        prev_img = None

        for i in xrange(first_index, count):
            adj_index = i - first_index
            logging.debug("Reading Frame %d", adj_index)

            fullpath = os.path.join(self.dest_dir, str(adj_index) + '.' +
                                    self.image_format)

            if i > 0 and checksums[i] == checksums[i-1]:
                logging.debug("Image the same as previous image, copying it...")

                prev_img.save(fullpath)

                logging.debug("Copied image and skipping iteration.")
                continue

            # current image is previous image for the next iteration
            prev_img = self.chameleon_port.read_captured_frame(i)

            prev_img.save(fullpath)

            test_images.append(fullpath)

        return test_images


    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.was_plugged:
            self.chameleon_port.unplug()