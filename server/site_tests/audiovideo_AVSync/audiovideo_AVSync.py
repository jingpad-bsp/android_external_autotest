# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import os
import struct
import time

from autotest_lib.server.cros.audio import audio_test

from autotest_lib.client.common_lib import file_utils
from autotest_lib.client.cros import constants
from autotest_lib.client.cros.chameleon import audio_test_utils
from autotest_lib.client.cros.chameleon import chameleon_port_finder
from autotest_lib.client.cros.chameleon import edid as edid_lib


class audiovideo_AVSync(audio_test.AudioTest):
    """ Server side HDMI audio/video sync quality measurement

    This test talks to a Chameleon board and a Cros device to measure the
    audio/video sync quality under playing a 1080p 60fps video.
    """
    version = 1

    AUDIO_RATE = 48000
    VIDEO_RATE = 60

    BEEP_THRESHOLD = 10 ** 9

    DELAY_BEFORE_CAPTURING = 2
    DELAY_BEFORE_PLAYBACK = 2
    DELAY_AFTER_PLAYBACK = 2

    DEFAULT_VIDEO_URL = ('http://commondatastorage.googleapis.com/'
                         'chromiumos-test-assets-public/chameleon/'
                         'audiovideo_AVSync/1080p.mp4')

    DISABLE_ACCELERATRED_VIDEO_DECODE_CHROME_KWARGS = {
        'extension_paths': [constants.MULTIMEDIA_TEST_EXTENSION],
        'extra_browser_args': ['--disable-accelerated-video-decode'],
        'clear_enterprise_policy': True,
        'arc_mode': 'disabled',
        'autotest_ext': True
    }


    def compute_audio_keypoint(self, data):
        """Compute audio keypoints. Audio keypoints are the starting times of
        beeps.

        @param data: Raw captured audio data in S32LE, 8 channels, 48000 Hz.

        @returns: Key points of captured data put in a list.
        """
        keypoints = []
        sample_no = 0
        last_beep_no = -100
        for i in xrange(0, len(data), 32):
            values = struct.unpack('<8i', data[i:i+32])
            if values[0] > self.BEEP_THRESHOLD:
                if sample_no - last_beep_no >= 100:
                    keypoints.append(sample_no / float(self.AUDIO_RATE))
                last_beep_no = sample_no
            sample_no += 1
        return keypoints


    def compute_video_keypoint(self, checksum):
        """Compute video keypoints. Video keypoints are the times when the
        checksum changes.

        @param checksum: Checksums of frames put in a list.

        @returns: Key points of captured video data put in a list.
        """
        return [i / float(self.VIDEO_RATE)
                for i in xrange(1, len(checksum))
                if checksum[i] != checksum[i - 1]]


    def log_result(self, prefix, key_audio, key_video, dropped_frame_count):
        """Log the test result to result.json and the dashboard.

        @param prefix: A string distinguishes between subtests.
        @param key_audio: Key points of captured audio data put in a list.
        @param key_video: Key points of captured video data put in a list.
        @param dropped_frame_count: Number of dropped frames.
        """
        log_path = os.path.join(self.resultsdir, 'result.json')
        diff = map(lambda x : x[0] - x[1], zip(key_audio, key_video))
        diff_range = max(diff) - min(diff)
        result = dict(
            key_audio=key_audio,
            key_video=key_video,
            av_diff=diff,
            diff_range=diff_range,
            dropped_frame_count=dropped_frame_count
        )
        result = json.dumps(result, indent=2)
        with open(log_path, 'w') as f:
            f.write(result)
        logging.info(str(result))

        dashboard_result = dict(
            diff_range=[diff_range, 'seconds'],
            max_diff=[max(diff), 'seconds'],
            min_diff=[min(diff), 'seconds'],
            average_diff=[sum(diff) / len(diff), 'seconds'],
            dropped_frame_count=[dropped_frame_count, 'frames']
        )
        for key, value in dashboard_result.iteritems():
            self.output_perf_value(description=prefix+key, value=value[0],
                                   units=value[1], higher_is_better=False)


    def run_once(self, host, video_hardware_acceleration=True,
                 video_url=DEFAULT_VIDEO_URL):
        """Running audio/video synchronization quality measurement

        @param host: A host object representing the DUT.
        @param video_hardware_acceleration: Enables the hardware acceleration
                                            for video decoding.
        @param video_url: The ULR of the test video.
        """
        factory = self.create_remote_facade_factory(host)

        chameleon_board = host.chameleon
        audio_facade = factory.create_audio_facade()
        browser_facade = factory.create_browser_facade()
        display_facade = factory.create_display_facade()

        audio_port_finder = chameleon_port_finder.ChameleonAudioInputFinder(
                chameleon_board)
        video_port_finder = chameleon_port_finder.ChameleonVideoInputFinder(
                chameleon_board, display_facade)
        audio_port = audio_port_finder.find_port('HDMI')
        video_port = video_port_finder.find_port('HDMI')

        chameleon_board.setup_and_reset(self.outputdir)

        if not video_hardware_acceleration:
            browser_facade.start_custom_chrome(
                    self.DISABLE_ACCELERATRED_VIDEO_DECODE_CHROME_KWARGS)

        local_path = os.path.join(
                self.bindir, 'test_data', 'video', 'test.mp4')
        file_utils.download_file(video_url, local_path)
        host.send_file(os.path.join(self.bindir, 'test_data', 'video'), '/tmp/')

        tab = browser_facade.new_tab(
                'file:///tmp/video/video.html')
        browser_facade.wait_for_javascript_expression(
                tab, 'typeof player !== \'undefined\'', 10)

        edid_path = os.path.join(
                self.bindir, 'test_data/edids/HDMI_DELL_U2410.txt')

        video_port.plug()
        with video_port.use_edid_file(edid_path):
            audio_facade.set_chrome_active_node_type('HDMI', None)
            audio_facade.set_chrome_active_volume(100)
            audio_test_utils.check_audio_nodes(
                    audio_facade, (['HDMI'], None))
            display_facade.set_mirrored(True)
            display_facade.set_fullscreen(True)
            video_port.start_monitoring_audio_video_capturing_delay()

            time.sleep(self.DELAY_BEFORE_CAPTURING)
            video_port.start_capturing_video((64, 64, 16, 16))
            audio_port.start_capturing_audio()

            time.sleep(self.DELAY_BEFORE_PLAYBACK)
            browser_facade.execute_javascript(tab, 'player.play();', 10)
            browser_facade.wait_for_javascript_expression(
                    tab, 'player.ended', 20)
            time.sleep(self.DELAY_AFTER_PLAYBACK)

            remote_path, _ = audio_port.stop_capturing_audio()
            video_port.stop_capturing_video()
            start_delay = video_port.get_audio_video_capturing_delay()

        local_path = os.path.join(self.resultsdir, 'recorded.raw')
        chameleon_board.host.get_file(remote_path, local_path)

        audio_data = open(local_path).read()
        video_data = video_port.get_captured_checksums()

        logging.info("audio capture %d bytes, %f seconds", len(audio_data),
                     len(audio_data) / float(self.AUDIO_RATE) / 32)
        logging.info("video capture %d frames, %f seconds", len(video_data),
                     len(video_data) / float(self.VIDEO_RATE))

        key_audio = self.compute_audio_keypoint(audio_data)
        key_video = self.compute_video_keypoint(video_data)
        # Use the capturing delay to align A/V
        key_video = map(lambda x: x + start_delay, key_video)

        dropped_frame_count = browser_facade.evaluate_javascript(tab,
                'player.webkitDroppedFrameCount', 10)

        prefix = 'hw_' if video_hardware_acceleration else 'sw_'
        self.log_result(prefix, key_audio, key_video, dropped_frame_count)
