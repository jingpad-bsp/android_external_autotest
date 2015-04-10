# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import errno
import hashlib
import logging
import math
import mmap
import os
import re
import urllib2

from contextlib import closing

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import chrome_binary_test


DOWNLOAD_BASE = ('http://commondatastorage.googleapis.com'
                 '/chromiumos-test-assets-public/')

VEA_BINARY = 'video_encode_accelerator_unittest'

LOG_FILE_SUFFIX = 'output.log'

# Performance keys
KEY_FPS = 'fps'

# These strings should match chromium/src/tools/perf/unit-info.json.
UNIT_MILLISECOND = 'milliseconds'
UNIT_MICROSECOND = 'us'
UNIT_FPS = 'fps'

RE_FPS = re.compile(r'^Measured encoder FPS: ([+\-]?[0-9.]+)$', re.MULTILINE)


def _remove_if_exists(filepath):
    try:
        os.remove(filepath)
    except OSError, e:
        if e.errno != errno.ENOENT:  # no such file
            raise


class video_VEAPerf(chrome_binary_test.ChromeBinaryTest):
    """
    This test monitors several performance metrics reported by Chrome test
    binary, video_encode_accelerator_unittest.
    """

    version = 1

    def _logperf(self, test_name, key, value, units, higher_is_better=False):
        description = '%s.%s' % (test_name, key)
        self.output_perf_value(
                description=description, value=value, units=units,
                higher_is_better=higher_is_better)


    def _analyze_fps(self, test_name, log_file):
        """
        Analyze FPS info from result log file.
        """
        with open(log_file, 'r') as f:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            fps = [float(m.group(1)) for m in RE_FPS.finditer(mm)]
            mm.close()
        if len(fps) != 1:
            raise error.TestError('Parsing FPS failed w/ %d occurrence(s).' %
                                  len(fps))
        self._logperf(test_name, KEY_FPS, fps[0], UNIT_FPS, True)


    def _get_profile_name(self, profile):
        """
        Gets profile name from a profile index.
        """
        if profile == 1:
            return 'h264'
        elif profile == 11:
            return 'vp8'
        else:
            raise error.TestError('Internal error.')


    def _convert_test_name(self, path, on_cloud, profile):
        """Converts source path to test name and output video file name.

        For example: for the path on cloud
            "tulip2/tulip2-1280x720-1b95123232922fe0067869c74e19cd09.yuv"

        We will derive the test case's name as "tulip2-1280x720.vp8" or
        "tulip2-1280x720.h264" depending on the profile. The MD5 checksum in
        path will be stripped.

        For the local file, we use the base name directly.

        @param path: The local path or download path.
        @param on_cloud: Whether the file is on cloud.
        @param profile: Profile index.

        @returns a pair of (test name, output video file name)
        """
        s = os.path.basename(path)
        name = s[:s.rfind('-' if on_cloud else '.')]
        profile_name = self._get_profile_name(profile)
        return (name + '_' + profile_name, name + '.' + profile_name)


    def _download_video(self, path_on_cloud, local_file):
        url = '%s%s' % (DOWNLOAD_BASE, path_on_cloud)
        logging.info('download "%s" to "%s"', url, local_file)

        md5 = hashlib.md5()
        with closing(urllib2.urlopen(url)) as r, open(local_file, 'w') as w:
            while True:
                content = r.read(4096)
                if not content:
                    break
                md5.update(content)
                w.write(content)
        md5sum = md5.hexdigest()
        if md5sum not in path_on_cloud:
            raise error.TestError('unmatched md5 sum: %s' % md5sum)


    def _get_result_filename(self, test_name, subtype, suffix):
        return os.path.join(self.resultsdir,
                            '%s_%s_%s' % (test_name, subtype, suffix))


    def _append_freon_switch_if_needed(self, cmd_line):
        if utils.is_freon():
            cmd_line.append('--ozone-platform=gbm')


    def _run_test_case(self, test_name, test_stream_data):
        """
        Runs a VEA unit test.

        @param test_name: Name of this test case.
        @param test_stream_data: Parameter to --test_stream_data in vea_unittest.
        """
        # Get FPS
        log_file = self._get_result_filename(test_name, 'fps', LOG_FILE_SUFFIX)
        cmd_line = [
            '--gtest_filter=EncoderPerf/*/0',
            '--test_stream_data=%s' % test_stream_data,
            '--output_log="%s"' % log_file]
        self._append_freon_switch_if_needed(cmd_line)
        self.run_chrome_test_binary(VEA_BINARY, ' '.join(cmd_line))
        self._analyze_fps(test_name, log_file)
        # TODO(jchuang): Get CPU time under specified FPS.
        # TODO(jchuang): Get per-frame encoder latency.


    @chrome_binary_test.nuke_chrome
    def run_once(self, test_cases):
        last_error = None
        for (path, on_cloud, width, height, bit_rate, profile) in test_cases:
            try:
                test_name, output_name = self._convert_test_name(
                    path, on_cloud, profile)
                if on_cloud:
                    input_path = os.path.join(self.tmpdir,
                                              os.path.basename(path))
                    self._download_video(path, input_path)
                else:
                    input_path = os.path.join(self.cr_source_dir, path)
                output_path = os.path.join(self.tmpdir, output_name)
                test_stream_data = '%s:%s:%s:%s:%s:%s' % (
                    input_path, width, height, profile, output_path, bit_rate)
                self._run_test_case(test_name, test_stream_data)
            except Exception as last_error:
                # Log the error and continue to the next test case.
                logging.exception(last_error)
            finally:
                if on_cloud:
                    _remove_if_exists(input_path)
                _remove_if_exists(output_path)

        if last_error:
            raise last_error

