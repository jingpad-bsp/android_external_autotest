# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ConfigParser
import datetime
import os

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import webpagereplay_wrapper
from autotest_lib.client.cros.chameleon import chameleon
from autotest_lib.client.cros.chameleon import chameleon_port_finder
from autotest_lib.client.cros.chameleon import chameleon_video_capturer
from autotest_lib.client.cros.graphics import graphics_utils
from autotest_lib.client.cros.multimedia import local_facade_factory
from autotest_lib.client.cros.video import chameleon_screenshot_capturer
from autotest_lib.client.cros.video import import_screenshot_capturer
from autotest_lib.client.cros.video import method_logger
from autotest_lib.client.cros.video import native_html5_player
from autotest_lib.client.cros.video import screenshot_file_namer
from autotest_lib.client.cros.video import sequence_generator
from autotest_lib.client.cros.video import video_screenshot_collector
from autotest_lib.client.cros.video import vimeo_player


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


    @method_logger.log
    def __init__(self, chrome, bin_dir, channel, video_name,
                 video_format=None, video_def=None):
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
        self.chrome = chrome
        self.tab = chrome.browser.tabs[0]
        self.http_server = chrome.browser.http_server
        self.bin_dir = bin_dir

        self.channel = channel

        # Configuration file names
        self.autotest_cros_video_dir = '/usr/local/autotest/cros/video'
        self.device_spec_filename = 'device_spec.conf'
        self.test_constants_filename = 'test_constants.conf'
        self.video_info_filename = 'video_spec.conf'
        self.channel_spec_filename = 'channel_spec.conf'

        # HTML file specs
        self.html_filename = ('vimeo.html' if video_name == 'vimeo' else
                              'video.html')

        self.device_under_test = None

        # Video specifications
        self.video_name = video_name
        self.video_format = video_format
        self.video_def = video_def
        self.time_format = '%H:%M:%S'
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

        # Stuff that was forgotten to initialize.
        self.bottom_pixels_to_crop = None
        self.chameleon_interface = None
        self.media_id = None
        self.media_length = None
        self.media_url = None
        self.screen_height_pixels = None
        self.screen_width_pixels = None
        self.time_btwn_polling_s = None
        self.time_out_events_s = None
        self.timeout_video_input_s = None
        self.top_pixels_to_crop = None

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

        self.chameleon_interface = self.parser.get(section,
                                                   'chameleon_interface')

        self.timeout_video_input_s = self.parser.getint(section,
                                                        'timeout_video_input_s')


    @method_logger.log
    def _load_device_info(self):
        """
        Reads device info configuration file and stores parameters.

        @raises TestError if device resolution was not read.

        """

        res = graphics_utils.get_display_resolution()

        if res is None:
            raise error.TestError('Expected a screen resolution. Got None.')

        self.screen_width_pixels = res[0]
        self.screen_height_pixels = res[1]

        # TODO(ihf): Remove this once "_freon" has been deprecated as a
        # variant name.
        dut = utils.get_current_board().replace('_freon', '')

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

        self.video_width = self.parser.getint(self.video_name, 'width')
        self.video_height = self.parser.getint(self.video_name, 'height')

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

        self.video_frame_count = self.parser.getint(self.channel,
                                                    'video_frame_count')


    @property
    def golden_images_remote_dir(self):
        """
        @return: path to the remote directory where golden images can be found.

        """
        return os.path.join(self.remote_golden_image_root_dir,
                            self.video_name,
                            self.video_format,
                            self.video_def,
                            'golden_images',
                            self.device_under_test)


    def make_screenshot_filenamer(self):
        """

        @return: ScreenShotFileNamer object.

        """
        return screenshot_file_namer.ScreenShotFileNamer(
                self.screenshot_image_format)


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


    @method_logger.log
    def make_chameleon_screenshot_capturer(self, hostname, args):
        """

        @param chrome: Chrome instance.
        @param hostname: string, DUT's hostname.
        @param args: string, arguments passed from autotest command. This
                      typically is the IP of the Chameleon board.

        @returns a ChameleonScreenshotCapturer object.

        """

        chameleon_board = chameleon.create_chameleon_board(hostname, args)
        facade = local_facade_factory.LocalFacadeFactory(
                self.chrome).create_display_facade()

        box = (0, self.top_pixels_to_crop, self.screen_width_pixels,
               self.screen_height_pixels - self.bottom_pixels_to_crop)

        return chameleon_screenshot_capturer.ChameleonScreenshotCapturer(
                chameleon_board,
                self.chameleon_interface,
                facade,
                self.test_working_dir,
                self.timeout_video_input_s,
                box)


    @method_logger.log
    def make_chameleon_video_capturer(self, hostname, args):
        """
        @param hostname: string, name of  host that chameleon is connected to.
        @param args: dictionary, key-value of pairs of additional arguments.
                     includes the ip the chameleon board itself.

        @returns: ChameleonVideoCapturer object.

        """
        chameleon_board = chameleon.create_chameleon_board(hostname, args)
        facade = local_facade_factory.LocalFacadeFactory(
                self.chrome).create_display_facade()
        finder = chameleon_port_finder.ChameleonVideoInputFinder(
                chameleon_board,
                facade)

        # TODO: mussa There is a banner that displays a warning that we are
        # ignoring certificates. Right now just crop it out, need to figure out
        # what to do about the banner, crop it out permanently or dig inside
        # chrome flags to figure out how to disable it

        box = (0, self.top_pixels_to_crop, self.video_width,
               self.top_pixels_to_crop + self.video_height)

        return chameleon_video_capturer.ChameleonVideoCapturer(
                chameleon_port=finder.find_port(
                        interface=self.chameleon_interface),
                display_facade=facade,
                dest_dir=self.test_working_dir,
                image_format=self.screenshot_image_format,
                timeout_input_stable_s=self.timeout_video_input_s,
                box=box)


    def make_import_screenshot_capturer(self):
        """
        @returns an ImportScreenShotCapturer configured according to values in
                 the config file

        """
        return import_screenshot_capturer.ImportScreenShotCapturer(
                self.test_working_dir,
                self.screen_height_pixels,
                self.top_pixels_to_crop,
                self.bottom_pixels_to_crop)


    def make_video_player(self):
        """
        @return: VimeoPlayer or HTML5Player depending on video being tested.

        """
        player = None
        args = {'tab': self.tab, 'full_url': self.media_url,
                'video_src_path': self.video_source_file,
                'video_id': self.media_id,
                'event_timeout': self.time_out_events_s,
                'polling_wait_time': self.time_btwn_polling_s}

        if self.video_name == 'bigbuck' or self.video_name == 'switch_res':
            player = native_html5_player.NativeHtml5Player(**args)

        elif self.video_name == 'vimeo':
            player = vimeo_player.VimeoPlayer(**args)

        return player


    def make_video_screenshot_collector(self, capturer, player):
        """
        Create an object to coordinate navigating video to specific times and
        taking screenshots.

        @param capturer: ImportScreenshotCapturer or ChameleonScreenshotCapturer
                         object.

        @param player: VideoPlayer, video player object to use.
        @returns an object that accepts timestamps as input and takes
        screenshots of a video at those times.

        """

        namer = self.make_screenshot_filenamer()

        return video_screenshot_collector.VideoScreenShotCollector(player,
                                                                   namer,
                                                                   capturer)


    @classmethod
    def make_webpagereplay_server(cls, video_name):
        """
        @param wpr_conf_filepath: Complete path to a WPR configuration file.
        @param video_name: string, name of the video being tested.
        @returns a ReplayServer object used to start WPR server on DUT.

        """

        wpr_conf_filepath = '/usr/local/autotest/cros/video/wpr.conf'
        section = 'archive_paths'

        parser = ConfigParser.SafeConfigParser()

        parser.read(wpr_conf_filepath)

        if parser.has_option(section, video_name):
            path = parser.get(section, video_name)
            return webpagereplay_wrapper.WebPageReplayWrapper(path)

        return webpagereplay_wrapper.NullWebPageReplayWrapper()