# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, os.path

from autotest_lib.client.cros.video import method_logger
from autotest_lib.client.common_lib import file_utils


class GoldenImageDownloader(object):
    """
    Downloads golden images to a local test directory.

    Encapsulates the directory hierarchy storing golden images in the cloud.

    This class provides a mapping from a timestamp to a corresponding golden
    image. It hides the details of the choices we have made to store these
    golden images. Should we need to reorganize this directory structure, we
    will this class to reflect the new path. The rest of the system should not
    be and is not affected by that change.

    """


    @method_logger.log
    def __init__(self, test_root_dir, remote_root_dir,
                 video_name, video_format, video_def, device_under_test,
                 screenshot_namer):
        """
        Constructor.

        @param test_root_dir: path, local root directory for test.
        @param remote_root_dir: path, remote root directory for test.
        @param video_name: string, name of video under test.
        @param video_format: string, format of video under test.
        @param video_def: string, definition of video under test. e.g: 720p.
        @param device_under_test: string, device being tested,
        @param screenshot_namer: object that determines the filename of a
        screenshot.

        """
        self.test_root_dir = test_root_dir
        self.remote_root_dir = remote_root_dir
        self.video_name = video_name
        self.video_format = video_format
        self.video_def = video_def
        self.device_under_test = device_under_test
        self.screenshot_namer = screenshot_namer


    @method_logger.log
    def download_image(self, timestamp):
        """
        Downloads an image given a particular timestamp.

        Finds the complete path in the cloud of an image taken at timestamp.

        Golden images are stored in the cloud. They are organized according to
        video names, formats, etc. This method knows the relative structure of
        organization of directories.

        @param timestamp: Time within video that we wish to get the image for.

        @returns a path the golden imaged downloaded to the device.

        """

        local_path = os.path.join(self.test_root_dir,
                                  'golden_images',
                                  self.screenshot_namer.get_filename(timestamp))

        remote_path = os.path.join(self.remote_root_dir,
                                   self.video_name,
                                   self.video_format,
                                   self.video_def,
                                   'golden_images',
                                   self.device_under_test,
                                   self.screenshot_namer.get_filename(
                                       timestamp))

        file_utils.download_file(remote_path, local_path)

        return local_path


    @method_logger.log
    def download_images(self, timestamps):
        """
        Downloads all images at given timestamps.

        @param timestamps: list of timedelta values for times in the video that
        we wish to get the image for.

        @returns a list of paths to golden images downloaded to the device.

        """
        return [self.download_image(t) for t in timestamps]