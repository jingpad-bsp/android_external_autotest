# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import os
import time

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import file_utils
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros.audio import audio_helper
from autotest_lib.client.cros.input_playback import keyboard
from autotest_lib.client.cros.power import power_test


class power_VideoPlayback(power_test.power_Test):
    """class for power_VideoPlayback test.
    """
    version = 1

    # list of video name and url.
    _VIDEOS = [
        ('h264_1080_30fps',
         'http://commondatastorage.googleapis.com/chromiumos-test-assets-public/traffic/traffic-1920x1080-8005020218f6b86bfa978e550d04956e.mp4'
        ),
        ('h264_1080_60fps',
         'http://commondatastorage.googleapis.com/chromiumos-test-assets-public/Shaka-Dash/1080_60_10s_600frames-c80aeceeabfc9fc18ed2f98f219c85af.mp4'
        ),
        ('h264_4k_30fps',
         'http://commondatastorage.googleapis.com/chromiumos-test-assets-public/traffic/traffic_3840x2160-32ec10f87ef369d0e5ec9c736d63cc58.mp4'
        ),
        ('h264_4k_60fps',
         'http://commondatastorage.googleapis.com/chromiumos-test-assets-public/Shaka-Dash/h264_4k_60_10s_600frames-ab1bfb374d2e408aac4a1beaa1aa0817.mp4'
        ),
        ('vp8_1080_30fps',
         'http://commondatastorage.googleapis.com/chromiumos-test-assets-public/traffic/traffic-1920x1080-ad53f821ff3cf8ffa7e991c9d2e0b854.vp8.webm'
        ),
        ('vp8_1080_60fps',
         'http://commondatastorage.googleapis.com/chromiumos-test-assets-public/Shaka-Dash/1080_60_10s_600frames_vp8-c190d557caaf415f762af911b41bc32b.webm'
        ),
        ('vp8_4k_30fps',
         'http://commondatastorage.googleapis.com/chromiumos-test-assets-public/Shaka-Dash/2160_vp8_600frames-3d61b1aed4e3f32249c7d324a809ef54.vp8.webm'
        ),
        ('vp8_4k_60fps',
         'http://commondatastorage.googleapis.com/chromiumos-test-assets-public/Shaka-Dash/vp8_4k_60_10s_600frames-b8d65f0eea64647be5413a75622abe79.webm'
        ),
        ('vp9_1080_30fps',
         'http://commondatastorage.googleapis.com/chromiumos-test-assets-public/traffic/traffic-1920x1080-83a1e5f8b7944577425f039034e64c76.vp9.webm'
        ),
        ('vp9_1080_60fps',
         'http://commondatastorage.googleapis.com/chromiumos-test-assets-public/video_tests/perf/fallout4_1080_hfr.vp9.webm'
        ),
        ('vp9_4k_30fps',
         'http://commondatastorage.googleapis.com/chromiumos-test-assets-public/traffic/traffic-3840x2160-cbcdda7d7143b3e9f8efbeed0c4157b5.vp9.webm'
        ),
        ('vp9_4k_60fps',
         'http://commondatastorage.googleapis.com/chromiumos-test-assets-public/Shaka-Dash/2160_60_10s_600frames-2fd17338cb4d9cfd9d7299a108ca9145.vp9.webm'
        ),
    ]

    # Ram disk location to download video file.
    # We use ram disk to avoid power hit from network / disk usage.
    _RAMDISK = '/tmp/ramdisk'

    # Time in seconds to wait after set up before starting test.
    _WAIT_FOR_IDLE = 10

    # Time in seconds to measure power per video file.
    _MEASUREMENT_DURATION = 30

    # Chrome arguemnts to disable HW video decode
    _DISABLE_HW_VIDEO_DECODE_ARGS = '--disable-accelerated-video-decode'

    def initialize(self, pdash_note=''):
        """Create and mount ram disk to download video."""
        super(power_VideoPlayback, self).initialize(seconds_period=5,
                                                    pdash_note=pdash_note)
        utils.run('mkdir -p %s' % self._RAMDISK)
        # Don't throw an exception on errors.
        result = utils.run('mount -t ramfs -o context=u:object_r:tmpfs:s0 '
                           'ramfs %s' % self._RAMDISK, ignore_status=True)
        if result.exit_status:
            logging.info('cannot mount ramfs with context=u:object_r:tmpfs:s0,'
                         ' trying plain mount')
            # Try again without selinux options.  This time fail on error.
            utils.run('mount -t ramfs ramfs %s' % self._RAMDISK)
        audio_helper.set_volume_levels(10, 10)

    def _play_video(self, cr, local_path):
        """Opens the video and plays it.

        @param cr: Autotest Chrome instance.
        @param local_path: path to the local video file to play.
        """
        tab = cr.browser.tabs[0]
        tab.Navigate(cr.browser.platform.http_server.UrlOf(local_path))
        tab.WaitForDocumentReadyStateToBeComplete()
        tab.EvaluateJavaScript("document.getElementsByTagName('video')[0]."
                               "loop=true")

    def _calculate_dropped_frame_percent(self, tab):
        """Calculate percent of dropped frame.

        @param tab: tab object that played video in Autotest Chrome instance.
        """
        decoded_frame_count = tab.EvaluateJavaScript(
                "document.getElementsByTagName"
                "('video')[0].webkitDecodedFrameCount")
        dropped_frame_count = tab.EvaluateJavaScript(
                "document.getElementsByTagName"
                "('video')[0].webkitDroppedFrameCount")
        if decoded_frame_count != 0:
            dropped_frame_percent = \
                    100.0 * dropped_frame_count / decoded_frame_count
        else:
            logging.error("No frame is decoded. Set drop percent to 100.")
            dropped_frame_percent = 100.0

        logging.info("Decoded frames=%d, dropped frames=%d, percent=%f",
                decoded_frame_count, dropped_frame_count, dropped_frame_percent)
        return dropped_frame_percent

    def run_once(self, videos=None, secs_per_video=_MEASUREMENT_DURATION,
                 use_hw_decode=True):
        """run_once method.

        @param videos: list of tuple of tagname and video url to test.
        @param secs_per_video: time in seconds to play video and measure power.
        @param use_hw_decode: if False, disable hw video decoding.
        """
        videos_local = []
        loop = 0

        if not videos:
            videos = self._VIDEOS

        # Download video to ramdisk
        for name, url in videos:
            local_path = os.path.join(self._RAMDISK, os.path.basename(url))
            logging.info('Downloading %s to %s', url, local_path)
            file_utils.download_file(url, local_path)
            videos_local.append((name, local_path))

        extra_browser_args = []
        if not use_hw_decode:
            extra_browser_args.append(self._DISABLE_HW_VIDEO_DECODE_ARGS)

        with chrome.Chrome(extra_browser_args=extra_browser_args,
                           init_network_controller=True) as self.cr:
            self.cr.browser.platform.SetHTTPServerDirectories(self._RAMDISK)
            tab = self.cr.browser.tabs.New()
            tab.Activate()

            # Just measure power in full-screen.
            fullscreen = tab.EvaluateJavaScript('document.webkitIsFullScreen')
            if not fullscreen:
                with keyboard.Keyboard() as keys:
                    keys.press_key('f4')

            time.sleep(self._WAIT_FOR_IDLE)
            self.start_measurements()

            for name, url in videos_local:
                logging.info('Playing video: %s', name)
                self._play_video(self.cr, url)
                tagname = '%s_%s' % (self.tagged_testname, name)
                loop_start = time.time()
                self.loop_sleep(loop, secs_per_video)
                self.keyvals[name + '_dropped_frame_percent'] = \
                        self._calculate_dropped_frame_percent(tab)
                self.checkpoint_measurements(tagname, loop_start)
                loop += 1

    def cleanup(self):
        """Unmount ram disk."""
        utils.run('umount %s' % self._RAMDISK)
        super(power_VideoPlayback, self).cleanup()
