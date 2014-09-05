# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import file_utils
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros.image_comparison import image_comparison_factory
from autotest_lib.client.cros.video import media_test_factory
from autotest_lib.client.cros.video import sequence_generator


class video_GlitchDetection(test.test):
    """
    Seeks video to random time instances and checks if the images shown at
    such respective times are expected.

    """

    version = 2

    def run_video_glitch_detection_test(self, browser, channel, video_name,
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
        @param video_name: Name of video to use for test
        @param video_def: Resolution of the video to test

        """

        test_factory = media_test_factory.MediaTestFactory(browser.tabs[0],
                                                      browser.http_server,
                                                      self.bindir, channel,
                                                      video_name,
                                                      video_format,
                                                      video_def)

        img_comp_conf_path = os.path.join(test_factory.autotest_cros_video_dir,
                                          'image_comparison.conf')

        img_comp_factory = image_comparison_factory.ImageComparisonFactory(
                img_comp_conf_path)

        bp_proj_specs = [img_comp_factory.bp_base_projname,
                         test_factory.device_under_test,
                         video_format,
                         video_def,
                         utils.get_chromeos_release_version().replace('.', '_')]

        bp_proj_name = '.'.join(bp_proj_specs)

        comparer = img_comp_factory.make_upload_on_fail_comparer(bp_proj_name)

        verifier = img_comp_factory.make_image_verifier(comparer)

        golden_image_downloader = test_factory.make_golden_image_downloader()
        screenshot_collector = test_factory.make_video_screenshot_collector()

        test_dir = test_factory.local_golden_images_dir

        file_utils.rm_dir_if_exists(test_dir)

        file_utils.make_leaf_dir(test_dir)

        file_utils.ensure_dir_exists(test_dir)

        timestamps = sequence_generator.generate_random_sequence(
                test_factory.start_capture,
                test_factory.stop_capture,
                test_factory.samples_per_min)

        golden_images = golden_image_downloader.download_images(timestamps)

        file_utils.ensure_all_files_exist(golden_images)

        screenshot_collector.ensure_player_is_ready()

        test_images = screenshot_collector.collect_multiple_screenshots(
                timestamps)

        file_utils.ensure_all_files_exist(test_images)

        verifier.verify(golden_images, test_images)

        file_utils.rm_dir_if_exists(test_dir)


    def run_once(self, channel, video_name, video_format, video_def):
        with chrome.Chrome() as cr:
            cr.browser.SetHTTPServerDirectories(self.bindir)
            self.run_video_glitch_detection_test(cr.browser,
                                                 channel,
                                                 video_name,
                                                 video_format,
                                                 video_def)
