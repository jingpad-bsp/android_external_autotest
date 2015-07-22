# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime, logging, os, time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import base_utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import file_utils
from autotest_lib.client.common_lib import sequence_utils
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros import constants, service_stopper
from autotest_lib.client.cros.image_comparison import image_comparison_factory
from autotest_lib.client.cros.video import media_test_factory
from autotest_lib.client.cros.video import sequence_generator


class video_GlitchDetection(test.test):
    """"
    Takes video frames/screenshots and compares them against known golden ones.

    Main test steps:
    1. Configure test, set up environment, create needed objects.
    2. Download golden images from cloud storage.
    4. Load the video based on received configuration (video_format, res)
    5. Capture images/frames for the video
    6. Verify that captured images/frames are the same as expected golden
    ones.
    The criteria to determine if two images are the same is read from the
    configuration above.
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
        if not self.collect_only: # keep images if you are collecting golden
        # images
            file_utils.rm_dir_if_exists(self.test_dir)


    def setup_image_capturing(self):
        """
        Set up the environment for capturing images.

        """
        self.player = self.factory.make_video_player()

        file_utils.make_leaf_dir(self.golden_images_dir)
        file_utils.rm_dir_if_exists(self.test_dir)
        file_utils.make_leaf_dir(self.golden_images_dir)
        file_utils.ensure_dir_exists(self.test_dir)


    def setup_image_comparison(self):
        """
        Create objects needed for image comparison.

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

        self.bp_comparer = img_comp_factory.make_bp_comparer(bp_proj_name)

        self.verifier = img_comp_factory.make_image_verifier(comparer)


    def run_screenshot_image_comparison_test(self):
        """
        Capture screenshots and compare against golden ones.

        """
        capturer = self.factory.make_import_screenshot_capturer()
        screenshot_collector = self.factory.make_video_screenshot_collector(
                capturer=capturer, player=self.player)

        timestamps = sequence_generator.generate_random_sequence(
                self.factory.start_capture,
                self.factory.stop_capture,
                self.factory.samples_per_min)

        test_images_paths = screenshot_collector.collect_multiple_screenshots(
                timestamps)

        namer = self.factory.make_screenshot_filenamer()
        filenames = [namer.get_filename(t) for t in timestamps]

        golden_images_paths = self.download_golden_images(filenames)

        self.verifier.verify(golden_images_paths, test_images_paths)


    def capture_frames(self):
        """
        Capture frames using chameleon.

        """
        self.video_capturer = self.factory.make_chameleon_video_capturer(
                self.host.hostname, self.chameleon_host_args)
        with self.video_capturer as c:
            self.player.load_video()
            self.player.play()
            utils.poll_for_condition(lambda : self.player.currentTime() > 0.0,
                                     timeout=5,
                                     exception=error.TestError(
                                             "Expected current time to be > 0"))
            self.player.pause()
            self.player.seek_to(datetime.timedelta(seconds=0))

            logging.debug("Wait for fullscreen notifications to go away.")
            time.sleep(5)

            return c.capture_only(self.player, self.factory.video_frame_count)


    def get_unique_checksum_indices(self, checksums):
        """
        Returns a list of checksum, first_occurance_index.
        @param checksums: list of checksums
        @return: list of checksum, first_occurance_index

        """
        prev_checksum = None
        checksum_index_list = []
        for i, checksum in enumerate(checksums):
            if checksum != prev_checksum:
                checksum_index_list.append((checksum, i))
                prev_checksum = checksum

        return checksum_index_list


    def collect_chameleon_golden_images(self):
        """
        Collect golden images but don't run any comparisons. Useful for creating
        new golden images.

        """
        checksums = self.capture_frames()
        checksum_index_list = self.get_unique_checksum_indices(checksums)

        # check that we don't have unexpected repeated frames
        self.ensure_expected_frame_repeat_count(
                checksum_index_list, self.factory.max_repeat_frame_count)

        indices = [entry[1] for entry in checksum_index_list]

        self.video_capturer.write_images(indices)

        golden_checksum_path = os.path.join(
                self.test_dir, self.factory.golden_checksum_filename)

        # write checksums to file
        logging.debug("Write golden checksum file to %s", golden_checksum_path)
        with open(golden_checksum_path, "w+") as f:
            for checksum, ind in checksum_index_list:
                f.write(' '.join([str(i) for i in checksum]))
                f.write(' | %d\n' % ind)


    def read_chameleon_golden_checksumfile(self, path):
        """
        Reads the golden checksum file. Each line in file has the format
        w x y z | count where w x y z is a chameleon frame checksum
        @param path: complete path to the golden checksum file.
        @return an OrderedDict of checksum -> count.

        """
        checksum_index_list = []
        with open(path) as f:
            for line in f:
                entry = line.split("|") # w x y z | count
                # turn into a tuple because a list can not be used a dict key
                checksum = [int(val) for val in entry[0].split()]
                checksum_index_list.append((checksum, int(entry[1])))

        return  checksum_index_list


    def ensure_expected_frame_repeat_count(self, checksum_indices,
                                           max_repeat_count):
        """
        Walks the list of checksum, first occurrence tuple to ensure that
        repeated counts of frames are reasonable.

        @param checksum_indices: list of tuples checksum, first index occurred.
        @param max_repeat_count: int, max. frame frequency allowed

        """

        for i in range(0, len(checksum_indices) - 1):
            checksum = checksum_indices[i][0]
            checksum_first_occurred = checksum_indices[i][1]
            next_checksum_first_occurred = checksum_indices[i + 1][1]
            repeat_count = (next_checksum_first_occurred -
                            checksum_first_occurred)
            if repeat_count > max_repeat_count:
                msg = ("Too many repeated frames for checksum %s! # of "
                       "repeated frames : %d. Max allowed is : %d"
                       %(checksum, repeat_count, max_repeat_count))
                raise error.TestFail(msg)


    def run_chameleon_image_comparison_test(self):
        """
        Capture frames. Perform image comparison. Also check that the number
        of frames is distributed as expected.

        """

        def dump_list(l):
            """
            Logs list line by line.

            @param l, the list to log.

            """
            for elem in l:
                logging.debug(elem)

        checksums = self.capture_frames()

        logging.debug("*** RAW checksums ***")
        dump_list(checksums)

        test_checksum_ind_list = self.get_unique_checksum_indices(checksums)

        logging.debug("*** FILTERED checksum ***")
        dump_list(test_checksum_ind_list)

        # We may get a frame that is repeated many times
        self.ensure_expected_frame_repeat_count(
                test_checksum_ind_list, self.factory.max_repeat_frame_count)

        logging.debug("Download golden checksum file.")
        remote_golden_checksum_path = os.path.join(
            self.remote_golden_images_dir, self.factory.golden_checksum_filename)

        golden_checksum_path = os.path.join(
                self.golden_images_dir, self.factory.golden_checksum_filename)

        file_utils.download_file(remote_golden_checksum_path,
                                 golden_checksum_path)

        golden_checksum_ind_list = self.read_chameleon_golden_checksumfile(
                golden_checksum_path)

        eps = self.factory.frame_count_deviation
        golden_count = len(golden_checksum_ind_list)
        test_count = len(test_checksum_ind_list)

        # We may get too little or too many test frames received
        if abs(golden_count - test_count) > eps:
            msg = ("Expecting about %d checksums, received %d. Allowed delta "
                   "is %d") % (golden_count, test_count, eps)
            raise error.TestFail(msg)


        """
        Find the length of a longest common subsequence (LCS) between golden
        and test checksums.
        Sometimes you have a missing frame or an extra frame in one list or the
        other. Using LCS we skip over the missing frame and continue the
        comparison on the rest of the list

        """

        # Use a tuple because we will need to hash the checksums into a set
        golden_checksums = [tuple(elem[0]) for elem in golden_checksum_ind_list]
        test_checksums = [tuple(elem[0]) for elem in test_checksum_ind_list]

        lcs_len = sequence_utils.lcs_length(golden_checksums, test_checksums)
        eps = self.factory.nonmatching_frames_eps

        missing_frames_count = len(golden_checksums) - lcs_len
        unknown_frames_count = len(test_checksums) - lcs_len

        msg = ("# of matching frames : %d. # of missing frames : %d. # of "
               "unknown test frames : %d. Max allowed # of missing frames : "
               "%d. # of golden frames : %d. # of test_checksums : %d"
               %(lcs_len, missing_frames_count, unknown_frames_count, eps,
                 len(golden_checksums), len(test_checksums)))

        logging.debug(msg)

        # get the checksums that are in test run but not in the golden run
        # they could be glitchy

        unknown_checksums = set(test_checksums) - set(golden_checksums)

        if missing_frames_count + unknown_frames_count > eps:
            # save it for later review, we are not really verifying,

            indices = [i for checksum, i in test_checksum_ind_list if tuple(
                checksum) in unknown_checksums]

            paths = self.video_capturer.write_images(indices)

            comp_url = ''
            for path in paths:
                comp_result = self.bp_comparer.compare(path, path)
                # need the parent link, should be just one for all comparisons
                if not comp_url:
                   comp_url = os.path.dirname(comp_result.comparison_url)

            raise error.TestFail("Too many non-matching frames! " + msg +
                                 " Comparison urls : " + comp_url)


    def download_golden_images(self, filepaths):
        """
        Downloads golden images corresponding to the captured test images.
        @param filepaths: list of golden image filepaths.
        @return: list of paths to downloaded golden images.

        """
        golden_images = []

        if type(filepaths) is not list:
            filepaths = [filepaths]

        filenames = [os.path.basename(path) for path in filepaths]

        for f in filenames:
            localpath = os.path.join(self.factory.local_golden_images_dir, f)
            remotepath = os.path.join(self.factory.golden_images_remote_dir, f)
            file_utils.download_file(remotepath, localpath)
            golden_images.append(localpath)

        return golden_images


    def run_once(self, channel, video_name, video_format='', video_def='',
                 collect_only=False, use_chameleon=False, host=None, args=None):

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
        self.video_format = video_format
        self.video_def = video_def
        self.use_chameleon = use_chameleon
        self.collect_only = collect_only

        do_not_scale_boards = ['link']
        this_board = utils.get_current_board()
        scale_args = ['--force-device-scale-factor', '1']

        browser_args = [] if this_board in do_not_scale_boards else scale_args

        self.chameleon_host_args = ""

        # when we are collecting images, we just have one control file, we will
        # receive different command line parameters so process those
        # args are delivered like this:
        # ['CHAMELEON_HOST=100.107.2.250,video_format=mp4,video_def=480p']
        video_args = {}
        if args:
            args = args[0].split(',')
            self.chameleon_host_args = [arg for arg in args if arg.lower().
                    startswith('chameleon_host')]
            video_args = base_utils.args_to_dict(args)
            # if args are provided use those instead
            if 'video_format' in video_args:
                self.video_format = video_args['video_format']

            if 'video_def' in video_args:
                self.video_def = video_args['video_def']

        ext_paths = []
        if use_chameleon:
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
                    video_format=self.video_format,
                    video_def=self.video_def)

            self.test_dir = self.factory.test_working_dir
            self.golden_images_dir = self.factory.local_golden_images_dir
            self.remote_golden_images_dir = self.factory.golden_images_remote_dir

            if not self.factory.is_board_supported:
                logging.debug("Board not supported. End Test.")
                return

            self.setup_image_capturing()

            if collect_only:
                self.collect_chameleon_golden_images()
            else:
                self.setup_image_comparison()

                if use_chameleon:
                    self.run_chameleon_image_comparison_test()

                else:
                    self.run_screenshot_image_comparison_test()