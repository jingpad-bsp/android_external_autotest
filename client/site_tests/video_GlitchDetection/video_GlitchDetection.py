# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import file_utils
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros import constants
from autotest_lib.client.cros.image_comparison import image_comparison_factory
from autotest_lib.client.cros.video import media_test_factory
from autotest_lib.client.cros.video import sequence_generator


class video_GlitchDetection(test.test):
    """
    Seeks video to random time instances and checks if the images shown at
    such respective times are expected.

    """

    version = 2

    def run_video_glitch_detection_test(self, chrome):
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

        @param chrome: Chrome instance

        """

        tab = chrome.browser.tabs[0]
        server = chrome.browser.http_server

        test_factory = media_test_factory.MediaTestFactory(tab,
                                                      server,
                                                      self.bindir,
                                                      self.channel,
                                                      self.video_name,
                                                      self.video_format,
                                                      self.video_def)

        img_comp_conf_path = os.path.join(test_factory.autotest_cros_video_dir,
                                          'image_comparison.conf')

        img_comp_factory = image_comparison_factory.ImageComparisonFactory(
                img_comp_conf_path)

        bp_proj_specs = [img_comp_factory.bp_base_projname,
                         test_factory.device_under_test,
                         self.video_format,
                         self.video_def,
                         utils.get_chromeos_release_version().replace('.', '_')]

        bp_proj_name = '.'.join(bp_proj_specs)

        comparer = img_comp_factory.make_upload_on_fail_comparer(bp_proj_name)

        verifier = img_comp_factory.make_image_verifier(comparer)

        golden_image_downloader = test_factory.make_golden_image_downloader()

        if self.use_chameleon:
            capturer = test_factory.make_chameleon_screenshot_capturer(
                    chrome=chrome,
                    hostname=self.host.hostname,
                    args=self.args)
        else:
            capturer = test_factory.make_import_screenshot_capturer()

        screenshot_collector = test_factory.make_video_screenshot_collector(
                capturer)

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

        test_images = screenshot_collector.collect_multiple_screenshots(
                timestamps)

        file_utils.ensure_all_files_exist(test_images)

        verifier.verify(golden_images, test_images)

        file_utils.rm_dir_if_exists(test_dir)


    def run_once(self, channel, video_name, video_format, video_def,
                 use_chameleon=False, host=None, args=None):

        """
        Work around. See crbug/404773. Some boards have a scaling factor that
        results in screenshots being larger than expected. (This factor was
        intentionally changed.
        To have the same canvas size we force the scale factor.
        This only affects hd devices on our list: nyan and pi and has no
        effect on sd devices.
        For link specifically, we don't force that factor has that causes
        the actual device resolution to change. We don't want that.
        """
        # TODO: mussa: Remove code if scale factor get reverted to prev value.

        self.host = host
        self.args = args
        self.channel = channel
        self.video_name = video_name
        self.video_format = video_format
        self.video_def = video_def
        self.use_chameleon = use_chameleon

        do_not_scale_boards = ['link']
        this_board = utils.get_current_board()
        scale_args = ['--force-device-scale-factor', '1']

        browser_args = [] if this_board in do_not_scale_boards else scale_args

        ext_paths = [constants.MULTIMEDIA_TEST_EXTENSION]

        with chrome.Chrome(extra_browser_args=browser_args,
                           extension_paths=ext_paths) as cr:
            cr.browser.SetHTTPServerDirectories(self.bindir)
            self.run_video_glitch_detection_test(cr)