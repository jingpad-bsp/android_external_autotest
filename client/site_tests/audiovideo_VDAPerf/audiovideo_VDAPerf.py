# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import errno
import hashlib
import logging
import os
import re
import urllib2

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import chrome_test

from contextlib import closing
from math import ceil, floor, sqrt

KEY_DELIVERY_TIME_FIRST = 'delivery_time.first'
KEY_DELIVERY_TIME_AVG = 'delivery_time.avg'
KEY_DELIVERY_TIME_STDEV = 'delivery_time.stdev'
KEY_DELIVERY_TIME_75 = 'delivery_time.percentile_0.75'
KEY_DELIVERY_TIME_50 = 'delivery_time.percentile_0.50'
KEY_DELIVERY_TIME_25 = 'delivery_time.percentile_0.25'
KEY_FRAME_DROP_RATE = 'frame_drop_rate'
KEY_CPU_KERNEL_USAGE = 'cpu_usage.kernel'
KEY_CPU_USER_USAGE = 'cpu_usage.user'

ONE_SECOND = 1000000 # in microseconds

DOWNLOAD_BASE = 'http://commondatastorage.googleapis.com/chromiumos-test-assets-public/'
BINARY = 'video_decode_accelerator_unittest'
FRAME_DELIVERY_LOG = 'frame_delivery.log'

TIME_BINARY = '/usr/local/bin/time'

TIME_LOG = 'time.log'

# The format used for 'time': <real time>, <kernel time>, <user time>
TIME_OUTPUT_FORMAT = '%e %S %U'

RE_FRAME_DELIVERY_TIME = re.compile('frame \d+: (\d+) us')

def _get_statistics(values):
    n = float(len(values))
    u = sum(values) / n
    u2 = sum([x * x for x in values]) / n
    return u, sqrt(u2 - u * u)


def _percentile(values, k):
    assert k >= 0 and k <= 1
    i = k * (len(values) - 1)
    c, f = int(ceil(i)), int(floor(i))

    if c == f: return values[c]
    return (i - f) * values[c] + (c - i) * values[f]


def _remove_if_exists(filepath):
    try:
        os.remove(filepath)
    except OSError, e:
        if e.errno != errno.ENOENT: # no such file
            raise


class audiovideo_VDAPerf(chrome_test.ChromeBinaryTest):
    """
    This test monitors several performance metrics reported by the
    "video_decode_accelerator_unittest".
    """

    version = 1
    _perf_keyval = {}


    def initialize(self, arguments=[]):
        chrome_test.ChromeBinaryTest.initialize(
            self,
            nuke_browser_norestart=True,
            skip_deps=False)


    def _logperf(self, name, key, value):
        self._perf_keyval['%s.%s' % (name, key)] = value


    def _analyze_frame_delivery_times(self, name, frame_delivery_times):

        # The average of the first frame delivery time.
        t = [x[0] for x in frame_delivery_times]
        self._logperf(name, KEY_DELIVERY_TIME_FIRST, sum(t) / len(t))

        # Flatten and sort the frame_delivery_times.
        t = sorted(sum(frame_delivery_times, []))

        # The average and standard deviation of frame delivery times.
        mean, stdev = _get_statistics(t)

        self._logperf(name, KEY_DELIVERY_TIME_AVG, mean)
        self._logperf(name, KEY_DELIVERY_TIME_STDEV, stdev)

        # The 25%, 50%, and 75% percentile of the frame delivery times.
        self._logperf(name, KEY_DELIVERY_TIME_75, _percentile(t, 0.75))
        self._logperf(name, KEY_DELIVERY_TIME_50, _percentile(t, 0.50))
        self._logperf(name, KEY_DELIVERY_TIME_25, _percentile(t, 0.25))


    def _analyze_frame_drop_rate(self, name, frame_num, frame_delivery_times):
        total = frame_num * len(frame_delivery_times)
        decoded = sum([len(x) for x in frame_delivery_times])

        drop_rate = float(total - decoded) / total
        self._logperf(name, KEY_FRAME_DROP_RATE, drop_rate)


    def _analyze_cpu_usage(self, name, time_log_file):
        with open(time_log_file) as f:
            content = f.read()
        r, s, u = content.split()
        self._logperf(name, KEY_CPU_USER_USAGE, float(u) / float(r))
        self._logperf(name, KEY_CPU_KERNEL_USAGE, float(s) / float(r))


    def _load_frame_delivery_times(self):
        """Gets the frame delivery times from the log_file.

        The first line is the frame number of the first decoder. For exmplae:
          frame count: 250
        It is followed by the delivery time of each frame. For example:
          frame 0000: 16123 us
          frame 0001: 16305 us
          :

        Then it is the frame number of the second decoder followed by the
        delivery times, and so on so forth.
        """
        result = []
        with open(FRAME_DELIVERY_LOG, 'r') as f:
            while True:
                line = f.readline()
                if not line: break
                _, count = line.split(':')
                times = []
                for i in xrange(int(count)):
                    line = f.readline()
                    m = RE_FRAME_DELIVERY_TIME.match(line)
                    assert m, 'invalid format: %s' % line
                    times.append(int(m.group(1)))
                result.append(times)
        return result


    def _get_test_case_name(self, path):
        """Gets the test_case_name from the video's path.

        For example: for the path
            "/crowd/crowd1080-1edaaca36b67e549c51e5fea4ed545c3.vp8"
        We will derive the test case's name as "crowd1080_vp8".
        """
        s = path.split('/')[-1] # get the filename
        return '%s_%s' % (s[:s.rfind('-')], s[s.rfind('.') + 1:])


    def _download_video(self, download_path, local_file):
        url = '%s%s' % (DOWNLOAD_BASE, download_path)
        logging.info('download "%s" to "%s"', url, local_file)

        md5 = hashlib.md5()
        with closing(urllib2.urlopen(url)) as r, open(local_file, 'w') as w:
            while True:
                content = r.read(4096)
                if not content: break
                md5.update(content)
                w.write(content)

        md5sum = md5.hexdigest()
        if md5sum not in download_path:
            raise error.TestError('unmatched md5 sum: %s' % md5sum)


    def _run_test_case(self, name, test_video_data, frame_num, rendering_fps):

        # Get frame delivery time, decode as fast as possible.
        _remove_if_exists(FRAME_DELIVERY_LOG)
        cmd_line = ('--test_video_data="%s" ' % test_video_data +
                    '--gtest_filter=DecodeVariations/*/0 ' +
                    '--disable_rendering ' +
                    '--frame_delivery_log="%s"' % FRAME_DELIVERY_LOG)
        self.run_chrome_binary_test(BINARY, cmd_line)

        frame_delivery_times = self._load_frame_delivery_times()
        self._analyze_frame_delivery_times(name, frame_delivery_times)

        # Get frame drop rate & CPU usage, decode at the specified fps
        _remove_if_exists(FRAME_DELIVERY_LOG)
        cmd_line = ('--test_video_data="%s" ' % test_video_data +
                    '--gtest_filter=DecodeVariations/*/0 ' +
                    ('--rendering_fps=%s ' % rendering_fps) +
                    '--frame_delivery_log="%s"' % FRAME_DELIVERY_LOG)
        time_cmd = ('%s -f "%s" -o "%s" ' %
                    (TIME_BINARY, TIME_OUTPUT_FORMAT, TIME_LOG))
        self.run_chrome_binary_test(BINARY, cmd_line, prefix=time_cmd)

        #Ignore if no log was generated, see comment above.
        frame_delivery_times = self._load_frame_delivery_times()
        self._analyze_frame_drop_rate(name, frame_num, frame_delivery_times)
        self._analyze_cpu_usage(name, TIME_LOG)


    def run_once(self, test_cases):

        last_error = None
        for (path, width, height, frame_num, frag_num, profile,
             fps)  in test_cases:
            name = self._get_test_case_name(path)
            video_path = os.path.join(self.bindir, '%s.download' % name)
            test_video_data = '%s:%s:%s:%s:%s:%s:%s:%s' % (
                video_path, width, height, frame_num, frag_num, 0, 0, profile)
            try:
                self._download_video(path, video_path)
                self._run_test_case(name, test_video_data, frame_num, fps)
            except Exception as last_error:
                # log the error and continue to the next test case.
                logging.exception(last_error)
            finally:
                _remove_if_exists(video_path)

        self.write_perf_keyval(self._perf_keyval)

        if last_error:
            raise # the last error
