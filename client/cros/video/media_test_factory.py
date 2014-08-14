# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ConfigParser
import datetime
import os

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.video import bp_image_comparer, \
    upload_on_fail_comparer, golden_image_downloader,\
    import_screenshot_capturer, media_player,\
    method_logger, rgb_image_comparer,\
    screenshot_file_namer, sequence_generator, verifier, \
    video_screenshot_collector


class MediaTestFactory(object):
    """

    Responsible for instantiating objects that are needed by other objects.

    We chose to use this approach in order to separate an object's creation
    from its use. Most of the classes built in this library demand their
    dependencies to be supplied in their constructors.
    Separating object creation from use enables us to build the rest
    of the system assuming we will be supplied with that we want.
    The factory takes care of supplying the needed dependencies.

    It will also isolate to one place that will be changed if we introduce new
    object that offer a different 'strategy' of doing things.

    For example new ways to compare images, we will build logic to decide
    which one here and then supply the client with an object that will do
    the comparison the 'correct' way.

    See make_capture_sequence_generator() below for an example. If test asks for
    a random capture sequence we will create that, or it wants an interval one
    we will create that. The client of the capture sequence will just *use* the
    sequence not caring whether it is random or it is with an interval.

    """


    BP_COMPARER = 'bp' # biopic comparer
    RGB_COMPARER = 'rgb_comparer' # RGB pixel by pixel comparer
    RGB_BP_COMPARER = 'rgb_bp_comparer' # RGB - local comparer, biopic - remote.


    @method_logger.log
    def __init__(self, tab, http_server, bin_dir, channel, video_name,
                 video_format, video_def):
        """
        Initializes factory.

        @param tab: object, tab of browser that will load the test page.
        @param http_server: object, http server to serve the test page
        @param bin_dir: path to autotest bin directory. This is where autotest
                        will put files that the library code depends on.
                        e.g:Configuration files
        @param channel: string, The channel of the build this test is running.
                        Configures how granular we want to collect screenshots.
                        See channel_spec.conf.
        @param video_format: string, format of the video.e.g: mp4
        @param video_def: string, definition of video. e.g: 480p

        Video format and definition will be used to find the path of the video
        source file stored in the cloud.

        """

        self.tab = tab
        self.http_server = http_server
        self.bin_dir = bin_dir

        self.channel = channel

        # Configuration file names
        self.autotest_cros_video_dir = '/usr/local/autotest/cros/video'
        self.device_spec_filename = 'device_spec.conf'
        self.test_constants_filename = 'test_constants.conf'
        self.video_info_filename = 'video_spec.conf'
        self.channel_spec_filename = 'channel_spec.conf'

        # HTML file specs
        self.html_filename = 'video.html'

        self.device_under_test = None

        # Video specifications
        self.video_name = video_name
        self.video_format = video_format
        self.video_def = video_def
        self.time_format = "%H:%M:%S"
        self.video_source_file = None

        # Test constants
        self.test_working_dir = None
        self.local_golden_images_dir = None
        self.remote_golden_image_root_dir = None

        # Screenshot capturing specs
        self.screenshot_image_format = None
        self.capture_sequence_style = None
        self.start_capture = None
        self.stop_capture = None
        self.samples_per_min = None
        self.capture_interval = None

        # Verification specs
        self.biopic_project_name = None
        self.biopic_contact_email = None
        self.biopic_wait_time = None
        self.biopic_num_upload_retries = None

        self.parser = None

        self._load_configuration()


    @method_logger.log
    def _load_configuration(self):
        """
        Loads all configuration parameters from specified configuration files.

        """

        self.parser = ConfigParser.SafeConfigParser()
        self._load_device_info()
        self._load_test_constants()
        self._load_video_info()
        self._load_channel_specs()


    @method_logger.log
    def _load_test_constants(self):
        """
        Reads test constants configuration file and stores parameters.

        """
        self.parser.read(os.path.join(self.autotest_cros_video_dir,
                                      self.test_constants_filename))

        # test_constants.conf has a constant section storing conf values
        section = 'constants'

        self.test_working_dir = self.parser.get(section, 'working_dir')

        self.local_golden_images_dir = self.parser.get(
                section, 'local_golden_images_dir')

        self.screenshot_image_format = self.parser.get(section, 'image_format')

        self.remote_golden_image_root_dir = self.parser.get(
                section, 'remote_golden_image_root_dir').replace('\n', '')

        self.media_id = self.parser.get(section, 'video_id')

        self.time_out_events_s = self.parser.getint(section,
                                                    'time_out_events_s')

        self.time_btwn_polling_s = self.parser.getfloat(section,
                                                        'time_btwn_polling_s')

        self.capture_sequence_style = self.parser.get(section,
                                                      'capture_sequence_style')

        version_nodots = utils.get_chromeos_release_version().replace('.', '_')

        biopic_proj_specs = [self.parser.get('biopic', 'project_name'),
                             self.device_under_test,
                             self.video_format,
                             self.video_def,
                             version_nodots]

        self.biopic_project_name = '.'.join(biopic_proj_specs)

        self.biopic_contact_email = self.parser.get('biopic', 'contact_email')
        self.biopic_wait_time = self.parser.getint('biopic',
                                                   'wait_time_btwn_comparisons')
        self.biopic_num_upload_retries = self.parser.getint('biopic',
                                                            'upload_retries')

        self.desired_comp_h = self.parser.getint('biopic', 'desired_comp_h')
        self.desired_comp_w = self.parser.getint('biopic', 'desired_comp_w')


    @method_logger.log
    def _load_device_info(self):
        """
        Reads device info configuration file and stores parameters.

        @raises TestError if device resolution was not read.

        """

        res = utils.get_dut_display_resolution()

        if res is None:
            raise error.TestError('Expected a screen resolution. Got None.')

        self.screen_height_pixels = res[1]
        dut = utils.get_current_board()

        self.parser.read(os.path.join(self.autotest_cros_video_dir,
                                      self.device_spec_filename))
        multires = self.parser.getboolean(dut, 'multires')

        if multires:
            dut += '_%d' % self.screen_height_pixels

        self.top_pixels_to_crop = self.parser.getint(dut, 'top_pixels_to_crop')

        self.bottom_pixels_to_crop = self.parser.getint(dut,
                                                        'bottom_pixels_to_crop')

        self.device_under_test = dut


    @method_logger.log
    def _load_video_info(self):
        """
        Reads video info configuration file and stores parameters.

        """
        self.parser.read(os.path.join(self.autotest_cros_video_dir,
                                      self.video_info_filename))

        length_str = self.parser.get(self.video_name, 'length')

        duration = datetime.datetime.strptime(length_str, self.time_format)

        self.media_length = datetime.timedelta(hours=duration.hour,
                                               minutes=duration.minute,
                                               seconds=duration.second)

        # We must have succeeded copying, save new file path
        http_fullpath = os.path.join(self.bin_dir, self.html_filename)

        self.media_url = self.http_server.UrlOf(http_fullpath)

        video_filename = '%s_%s.%s' % (self.video_name,
                                       self.video_def,
                                       self.video_format)

        self.video_source_file = os.path.join(self.remote_golden_image_root_dir,
                                              self.video_name,
                                              self.video_format,
                                              self.video_def,
                                              video_filename)


    @method_logger.log
    def _load_channel_specs(self):
        """
        Reads channel info configuration file and stores parameters.

        """
        self.parser.read(os.path.join(self.autotest_cros_video_dir,
                                      self.channel_spec_filename))

        self.samples_per_min = self.parser.getint(self.channel,
                                                  'samples_per_min')

        self.start_capture = datetime.timedelta(seconds=1)

        duration_in_minutes = self.parser.getfloat(self.channel,
                                                   'duration_in_minutes')

        self.stop_capture = (self.start_capture +
                             datetime.timedelta(minutes=duration_in_minutes))

        self.stop_capture = min(self.stop_capture, self.media_length)


    def make_golden_image_downloader(self):
        """
        @returns a golden image downloader based on configuration data.

        """
        return golden_image_downloader.GoldenImageDownloader(
                self.test_working_dir,
                self.remote_golden_image_root_dir,
                self.video_name,
                self.video_format,
                self.video_def,
                self.device_under_test,
                screenshot_file_namer.ScreenShotFileNamer(
                        self.screenshot_image_format))


    def make_capture_sequence_generator(self):
        """
        Create a (time) sequence generator based on configuration data.

        Create a random sequence generator if 'random' is specified else create
        an interval one.

        Note that we expect the client to specify capture_sequence_style.

        @returns an object that can generate a sequence of timestamps.

        """
        gn = None
        style = self.capture_sequence_style

        if style == 'random':
            gn = sequence_generator.RandomSequenceGenerator(
                    self.start_capture,
                    self.stop_capture,
                    self.samples_per_min)
        elif style == 'interval':
            gn = sequence_generator.IntervalSequenceGenerator(
                    self.start_capture,
                    self.stop_capture,
                    self.capture_interval)

        return gn


    def make_video_screenshot_collector(self):
        """
        Create an object to coordinate navigating video to specific times and
        taking screenshots.

        @returns an object that accepts timestamps as input and takes
        screenshots of a video at those times.

        """
        player = media_player.VideoPlayer(self.tab,
                                          self.media_url,
                                          self.video_source_file,
                                          self.media_id,
                                          self.time_out_events_s,
                                          self.time_btwn_polling_s)

        namer = screenshot_file_namer.ScreenShotFileNamer(
                self.screenshot_image_format)

        capturer = import_screenshot_capturer.ImportScreenShotCapturer(
                self.test_working_dir,
                self.screen_height_pixels,
                self.top_pixels_to_crop,
                self.bottom_pixels_to_crop)

        return video_screenshot_collector.VideoScreenShotCollector(player,
                                                                   namer,
                                                                   capturer)


    def make_bp_image_comparer(self):
        """
        @return: a bp-based image comparer.

        """
        return bp_image_comparer.BpImageComparer(self.biopic_project_name,
                                                 self.biopic_contact_email,
                                                 self.biopic_wait_time,
                                                 self.biopic_num_upload_retries)


    def make_image_verifier(self, comparer_to_use, stop_on_first_failure=False):
        """
        Creates a verifier to verify test images against reference images.

        @param comparer_to_use: string, type of image comparer desired.
        @param stop_on_first_failure: stop test on first test image that is not
                                      equal to a golden image.

        @return: object, a verifier object.

        """

        comparer = None

        if comparer_to_use == MediaTestFactory.BP_COMPARER:
            comparer = self.make_bp_image_comparer()

        elif comparer_to_use == MediaTestFactory.RGB_COMPARER:
            comparer = rgb_image_comparer.RGBImageComparer()

        elif comparer_to_use == MediaTestFactory.RGB_BP_COMPARER:
            comparer = upload_on_fail_comparer.UploadOnFailComparer(
                    rgb_image_comparer.RGBImageComparer(),
                    self.make_bp_image_comparer())

        box = (0, 0, self.desired_comp_w, self.desired_comp_h)

        return verifier.Verifier(comparer, stop_on_first_failure, box=box)
