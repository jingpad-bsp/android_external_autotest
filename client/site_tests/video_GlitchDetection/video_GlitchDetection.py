# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import file_utils
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros.video import sequence_generator,\
    media_test_factory


class video_GlitchDetection(test.test):
    """
    Seeks video to random time instances and checks if the images shown at
    such respective times are expected.

    """

    version = 2

    def run_video_glitch_detection_test(self, browser, channel,
                                        video_format, video_def):
        """
        Takes video screenshots and compares them against known golden images.

        Main test steps:
        1. Configure test, set up environment, create needed objects.
        2. Generate sequence of time instance to capture images.
        (This sequence will be generated based on configuration above.)
        3. Download golden images for time instances above from cloud storage.
        4. Load the video based on received configuration (video_format, res)
        5. Capture screenshots for each of generated time instances above.
        6. Verify that captured screenshots are the same as expected golden
        screenshots downloaded earlier.
        The criteria to determine if two images are the same is read from the
        configuration above.

        @param browser: Object to interact with Chrome browser
        @param channel: The channel we are running on: dev, beta
                        This is used to choose how many screenshots we will take
        @param video_format: Format of the video to test
        @param video_def: Resolution of the video to test

        """

        factory = media_test_factory.MediaTestFactory(browser.tabs[0],
                                                      browser.http_server,
                                                      self.bindir, channel,
                                                      video_format,
                                                      video_def)

        golden_image_downloader = factory.make_golden_image_downloader()
        screenshot_collector = factory.make_video_screenshot_collector()

        test_dir = factory.local_golden_images_dir

        file_utils.rm_dir_if_exists(test_dir)

        file_utils.make_leaf_dir(test_dir)

        file_utils.ensure_dir_exists(test_dir)

        timestamps = sequence_generator.generate_random_sequence(
                factory.start_capture,
                factory.stop_capture,
                factory.samples_per_min)

        golden_images = golden_image_downloader.download_images(timestamps)

        file_utils.ensure_all_files_exist(golden_images)

        screenshot_collector.ensure_player_is_ready()

        test_images = screenshot_collector.collect_multiple_screenshots(
                timestamps)

        file_utils.ensure_all_files_exist(test_images)

        with factory.make_image_comparer() as comparer:
            comparer.compare(golden_images, test_images)

        file_utils.rm_dir_if_exists(test_dir)


    def run_once(self, channel, video_format, video_def):
        with chrome.Chrome() as cr:
            cr.browser.SetHTTPServerDirectories(self.bindir)
            self.run_video_glitch_detection_test(cr.browser, channel,
                                                 video_format, video_def)
