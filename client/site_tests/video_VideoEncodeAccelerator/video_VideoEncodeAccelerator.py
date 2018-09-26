# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import errno
import fnmatch
import hashlib
import logging
import os
import subprocess

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import file_utils
from autotest_lib.client.cros import chrome_binary_test
from autotest_lib.client.cros.video import device_capability
from autotest_lib.client.cros.video import helper_logger

DOWNLOAD_BASE = 'http://commondatastorage.googleapis.com/chromiumos-test-assets-public/'
BINARY = 'video_encode_accelerator_unittest'

# These default values are from video_encode_accelerator_unittest.
# The value of |requested_frame_rate| and |requested_subsequent_frame_rate|.
DEFAULT_FRAME_RATE = 30
# The ratio of |requested_subsequent_bit_rate| to |requested_bit_rate|.
DEFAULT_SUBSEQUENT_BIT_RATE_RATIO = 2

def _remove_if_exists(filepath):
    try:
        os.remove(filepath)
    except OSError, e:
        if e.errno != errno.ENOENT: # no such file
            raise


def _download_video(download_path, local_file):
    url = '%s%s' % (DOWNLOAD_BASE, download_path)
    logging.info('download "%s" to "%s"', url, local_file)

    file_utils.download_file(url, local_file)

    with open(local_file, 'r') as r:
        md5sum = hashlib.md5(r.read()).hexdigest()
        if md5sum not in download_path:
            raise error.TestError('unmatched md5 sum: %s' % md5sum)

def _run_on_intel_cpu():
    try:
        lscpu_result = subprocess.check_output(['lscpu'])
    except subprocess.CalledProcessError:
        logging.warning('lscpu failed.')
        return False
    for cpu_info in lscpu_result.splitlines():
        key, _, value = cpu_info.partition(':')
        if key == 'Model name':
            return value.strip().startswith('Intel(R)')
    logging.warning("%s", lscpu_result)
    return False


class video_VideoEncodeAccelerator(chrome_binary_test.ChromeBinaryTest):
    """
    This test is a wrapper of the chrome unittest binary:
    video_encode_accelerator_unittest.
    """

    version = 1

    def get_filter_option(self, profile, size):
        """Get option of filtering test.

        @param profile: The profile to encode into.
        @param size: The size of test stream in pair format (width, height).
        """

        # Profiles used in blacklist to filter test for specific profiles.
        H264 = 1
        VP8 = 11
        VP9 = 12

        blacklist = {
                # (board, profile, size): [tests to skip...]

                # "board" supports Unix shell-type wildcards.

                # Use None for "profile" or "size" to indicate no filter on it.

                # It is possible to match multiple keys for board/profile/size
                # in the blacklist, e.g. veyron_minnie could match both
                # "veyron_*" and "veyron_minnie".

                # rk3399 doesn't support HW encode for plane sizes not multiple
                # of cache line.
                ('kevin', None, None): ['CacheLineUnalignedInputTest/*'],
                ('bob', None, None): ['CacheLineUnalignedInputTest/*'],
                ('scarlet', None, None): ['CacheLineUnalignedInputTest/*'],

                # Still high failure rate of VP8 EncoderPerf for veyrons,
                # disable it for now. crbug/720386
                ('veyron_*', VP8, None): ['EncoderPerf/*'],

                # Disable mid_stream_bitrate_switch test cases for elm/hana.
                # crbug/725087
                ('elm', None, None): ['MidStreamParamSwitchBitrate/*',
                                      'MultipleEncoders/*'],
                ('hana', None, None): ['MidStreamParamSwitchBitrate/*',
                                       'MultipleEncoders/*'],

                # Around 40% failure on elm and hana 320x180 test stream.
                # crbug/728906
                ('elm', H264, (320, 180)): ['ForceBitrate/*'],
                ('elm', VP8, (320, 180)): ['ForceBitrate/*'],
                ('hana', H264, (320, 180)): ['ForceBitrate/*'],
                ('hana', VP8, (320, 180)): ['ForceBitrate/*'],
                }

        board = utils.get_current_board()

        # Disable 320x180 test case. Bitrate of vp8 encoder on the test case is
        # out of expected range. b/110059922
        # TODO(hiroh): Remove this once b/110059922 is fixed.
        if _run_on_intel_cpu():
            blacklist[(board, VP8, (320, 180))] = ['*']

        filter_list = []
        for (board_key, profile_key, size_key), value in blacklist.items():
            if (fnmatch.fnmatch(board, board_key) and
                (profile_key is None or profile == profile_key) and
                (size_key is None or size == size_key)):
                filter_list += value

        if filter_list:
            return '-' + ':'.join(filter_list)

        return ''

    @helper_logger.video_log_wrapper
    @chrome_binary_test.nuke_chrome
    def run_once(self, in_cloud, streams, profile, capability,
                 gtest_filter=None):
        """Runs video_encode_accelerator_unittest on the streams.

        @param in_cloud: Input file needs to be downloaded first.
        @param streams: The test streams for video_encode_accelerator_unittest.
        @param profile: The profile to encode into.
        @param gtest_filter: test case filter.

        @raises error.TestFail for video_encode_accelerator_unittest failures.
        """
        device_capability.DeviceCapability().ensure_capability(capability)

        last_test_failure = None
        for (path, width, height, bit_rate, frame_rate, subsequent_bit_rate,
             subsequent_frame_rate) in streams:
            # Set the default value for None.
            frame_rate = frame_rate or DEFAULT_FRAME_RATE
            subsequent_bit_rate = (subsequent_bit_rate or
                                   bit_rate * DEFAULT_SUBSEQUENT_BIT_RATE_RATIO)
            subsequent_frame_rate = subsequent_frame_rate or DEFAULT_FRAME_RATE

            if in_cloud:
                input_path = os.path.join(self.tmpdir, path.split('/')[-1])
                _download_video(path, input_path)
            else:
                input_path = os.path.join(self.cr_source_dir, path)

            output_path = os.path.join(self.tmpdir,
                    '%s.out' % input_path.split('/')[-1])

            test_stream_list = map(
                    str, [input_path, width, height, profile, output_path,
                          bit_rate, frame_rate, subsequent_bit_rate,
                          subsequent_frame_rate])
            cmd_line_list = [
                    '--test_stream_data="%s"' % ':'.join(test_stream_list),
                    '--ozone-platform=gbm',
                    helper_logger.chrome_vmodule_flag()]

            # Command line |gtest_filter| can override get_filter_option().
            predefined_filter = self.get_filter_option(profile, (width, height))
            if gtest_filter and predefined_filter:
                logging.warning('predefined gtest filter is suppressed: %s',
                    predefined_filter)
                applied_filter = gtest_filter
            else:
                applied_filter = predefined_filter
            if applied_filter:
                cmd_line_list.append('--gtest_filter="%s"' % applied_filter)

            cmd_line = ' '.join(cmd_line_list)
            try:
                self.run_chrome_test_binary(BINARY, cmd_line, as_chronos=False)
            except error.TestFail as test_failure:
                # Continue to run the remaining test streams and raise
                # the last failure after finishing all streams.
                logging.exception('error while encoding %s', input_path)
                last_test_failure = test_failure
            finally:
                # Remove the downloaded video
                if in_cloud:
                    _remove_if_exists(input_path)
                _remove_if_exists(output_path)

        if last_test_failure:
            raise last_test_failure
