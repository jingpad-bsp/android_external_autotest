# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import file_utils
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros import constants, service_stopper
from autotest_lib.client.cros.image_comparison import image_comparison_factory
from autotest_lib.client.cros.video import media_test_factory
from autotest_lib.client.cros.video import sequence_generator


class video_GlitchDetection(test.test):
    """
    Seeks video to random time instances and checks if the images shown at
    such respective times are expected.

    """

    version = 2


    def initialize(self):
        """Perform necessary initialization prior to test run.

        Private Attributes:
          _services: service_stopper.ServiceStopper object
        """
        # Do not switch off screen for screenshot utility.
        self._services = service_stopper.ServiceStopper(['powerd'])
        self._services.stop_services()


    def cleanup(self):
        self._services.restore_services()


    def run_video_glitch_detection_test(self):
        """
        Takes video screenshots and compares them against known golden images.

        Main test steps:
        1. Configure test, set up environment, create needed objects.
        2. Download golden images from cloud storage.
        4. Load the video based on received configuration (video_format, res)
        5. Capture images/frames for the video
        6. Verify that captured images/frames are the same as expected golden
        ones.
        The criteria to determine if two images are the same is read from the
        configuration above.

        @param chrome: Chrome instance

        """
        img_comp_conf_path = os.path.join(self.factory.autotest_cros_video_dir,
                                          'image_comparison.conf')

        img_comp_factory = image_comparison_factory.ImageComparisonFactory(
                img_comp_conf_path)

        bp_proj_specs = [img_comp_factory.bp_base_projname,
                         self.factory.device_under_test,
                         self.video_format,
                         self.video_def,
                         utils.get_chromeos_release_version().replace('.', '_')]

        bp_proj_name = '.'.join(bp_proj_specs)

        comparer = img_comp_factory.make_upload_on_fail_comparer(bp_proj_name)

        verifier = img_comp_factory.make_image_verifier(comparer)

        self.player = self.factory.make_video_player()

        test_dir = self.factory.test_working_dir
        golden_images_dir = self.factory.local_golden_images_dir

        file_utils.rm_dir_if_exists(test_dir)

        file_utils.make_leaf_dir(golden_images_dir)

        file_utils.ensure_dir_exists(test_dir)

        golden_images = self.get_golden_images()

        test_images = self.get_test_images()

        file_utils.ensure_all_files_exist(golden_images)

        file_utils.ensure_all_files_exist(test_images)

        verifier.verify(golden_images, test_images)

        file_utils.rm_dir_if_exists(test_dir)


    def get_golden_images(self):
        if self.use_chameleon:
            filenames = [str(i) + '.' + self.factory.screenshot_image_format
                         for i in xrange(0, self.factory.video_frame_count)]

        else:
            timestamps = sequence_generator.generate_random_sequence(
                    self.factory.start_capture,
                    self.factory.stop_capture,
                    self.factory.samples_per_min)


            namer = self.factory.make_screenshot_filenamer()

            filenames = [namer.get_filename(t) for t in timestamps]


        golden_images_dir = self.factory.local_golden_images_dir
        golden_images = []

        for f in filenames:
            local_path = os.path.join(golden_images_dir, f)
            remote_path = os.path.join(self.factory.golden_images_remote_dir, f)

            file_utils.download_file(remote_path, local_path)

            golden_images.append(local_path)

        return golden_images


    def get_test_images(self):

        if self.use_chameleon:
            video_capturer = self.factory.make_chameleon_video_capturer(
            self.host.hostname, self.args)

            with video_capturer:
                self.player.load_video()

                test_images = video_capturer.capture(
                        self.player,
                        self.factory.video_frame_count)

        else:
            capturer = self.factory.make_import_screenshot_capturer()
            screenshot_collector = self.factory.make_video_screenshot_collector(
                    capturer=capturer, player=self.player)

            timestamps = sequence_generator.generate_random_sequence(
                    self.factory.start_capture,
                    self.factory.stop_capture,
                    self.factory.samples_per_min)

            test_images = screenshot_collector.collect_multiple_screenshots(
                    timestamps)


        return test_images


    def run_once(self, channel, video_name, video_format='', video_def='',
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
        self.video_format = video_format
        self.video_def = video_def
        self.use_chameleon = use_chameleon

        do_not_scale_boards = ['link']
        this_board = utils.get_current_board()
        scale_args = ['--force-device-scale-factor', '1']

        browser_args = [] if this_board in do_not_scale_boards else scale_args

        ext_paths = [constants.MULTIMEDIA_TEST_EXTENSION]

        wpr_server = (media_test_factory.MediaTestFactory
                      .make_webpagereplay_server(video_name))

        browser_args += wpr_server.chrome_flags_for_wpr

        with chrome.Chrome(extra_browser_args=browser_args,
                           extension_paths=ext_paths) as cr, wpr_server:
            cr.browser.SetHTTPServerDirectories(self.bindir)

            self.factory = media_test_factory.MediaTestFactory(
                    chrome=cr,
                    bin_dir=self.bindir,
                    channel=channel,
                    video_name=video_name,
                    video_format=video_format,
                    video_def=video_def)

            self.run_video_glitch_detection_test()