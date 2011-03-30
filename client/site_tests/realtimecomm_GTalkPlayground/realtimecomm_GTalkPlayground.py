# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, re, shutil, sys, time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import constants, cros_ui, cros_ui_test, httpd

WARMUP_TIME = 60
SLEEP_DURATION = 260
GTALK_LOG_PATH = '/tmp/gtalkplugin.log'

class realtimecomm_GTalkPlayground(cros_ui_test.UITest):
    version = 1
    dep = 'realtimecomm_playground'

    def setup(self):
        self.playground = os.path.join(self.autodir, 'playground')
        self.job.setup_dep([self.dep])


    def initialize(self, creds=None):
        self.dep_dir = os.path.join(self.autodir, 'deps', self.dep)

        # Start local HTTP server to serve playground.
        self._test_server = httpd.HTTPListener(
            port=80, docroot=os.path.join(self.dep_dir, 'src'))
        self._test_server.run()

        # We need the initialize call to use empty creds (a guest account)
        # so that the auth service isn't started on port 80, preventing
        # the server we are trying to run from binding to the same port.
        super(realtimecomm_GTalkPlayground, self).initialize(creds=None)

        # Since the DNS redirection is only activated implicitly when the
        # auth service is used, start it up explicitly.
        super(realtimecomm_GTalkPlayground, self).use_local_dns()


    def cleanup(self):
        self._test_server.stop()
        super(realtimecomm_GTalkPlayground, self).cleanup()


    def run_verification(self):
        # TODO(zhurun): Add more checking and perf data collection.
        if not os.path.exists(GTALK_LOG_PATH):
            raise error.TestFail('GTalk log file not exist!')
        content = utils.read_file(GTALK_LOG_PATH)
        if not "Found V4L2 capture" in content:
            raise error.TestFail('V4L2 not found!')
        if not "video state, recv=1 send=1" in content:
            raise error.TestFail('Error in Video send/recv!')
        if not "voice state, recv=1 send=1" in content:
            raise error.TestFail('Error in Audio send/recv!')
        if not "Decoded framerate" in content:
            raise error.TestFail('Error in Video upstream!')
        if not "Rendered framerate" in content:
            raise error.TestFail('Error in Video downstream!')
        # Get framerate
        self.get_framerate(content)


    def get_framerate(self, log):
        d = {}
        # We get a framerate report every 10 seconds for both streams.
        # We run for 5 mins, and should get around (5 * 60/10) * 2 = 60
        # framerate reports for 2 streams. Since this is an estimate,
        # expect the frames to be at least 90% of that count.
        expected_frame_count = (WARMUP_TIME + SLEEP_DURATION) / 10 * 2 * .9

        l = re.findall(r'Rendered framerate \((.*)\): (\d+\.?\d*) fps', log)
        if len(l) < expected_frame_count:
            raise error.TestFail('Error in Video duration!')

        # Ignore the first and last framerate since they are not accurate.
        for i in range(1, len(l) - 1):
            if d.has_key(l[i][0]):
                d[l[i][0]] = d[l[i][0]] + float(l[i][1])
            else:
                d[l[i][0]] = float(l[i][1])
        if len(d) != 2:
            raise error.TestFail('Number of video stream is NOT 2!')
        # Get framerate for two streams.
        fps = []
        for k in d:
           fps.insert(0, d[k] * 2 / (len(l) - 2))
        self.performance_results['fps_gtalk_up'] = max(fps[0], fps[1])
        self.performance_results['fps_gtalk_down'] = min(fps[0], fps[1])
        # Very low framerate means something wrong. Video hang or crash.
        if (min(fps[0], fps[1]) < 5.0):
            raise error.TestFail('Error in Video framerate.')


    def run_once(self):
        sys.path.append(self.dep_dir)
        import pgutil

        self.performance_results = {}
        pgutil.cleanup_playground(self.playground)
        pgutil.setup_playground(
            os.path.join(self.dep_dir, 'src'), self.playground,
            os.path.join(self.bindir, 'options'))

        try:
            # Launch Playground
            # Though we are using talk.google.com, this will be redirected
            # to localhost, via DNS redirection
            session = cros_ui.ChromeSession(
                'http://talk.google.com/'
                'buzz/javascript/media/examples/'
                'videoplayground.html?callType=v')

            # Collect ctime,stime for GoogleTalkPlugin
            time.sleep(WARMUP_TIME)
            gtalk_s = pgutil.get_utime_stime(
                pgutil.get_pids('GoogleTalkPlugin'))
            chrome_s = pgutil.get_utime_stime(
                pgutil.get_pids(constants.BROWSER))
            time.sleep(SLEEP_DURATION)
            gtalk_e = pgutil.get_utime_stime(
                pgutil.get_pids('GoogleTalkPlugin'))
            chrome_e = pgutil.get_utime_stime(
                pgutil.get_pids(constants.BROWSER))

            self.performance_results['ctime_gtalk'] = \
                pgutil.get_cpu_usage(SLEEP_DURATION, gtalk_e[0] - gtalk_s[0])
            self.performance_results['stime_gtalk'] = \
                pgutil.get_cpu_usage(SLEEP_DURATION, gtalk_e[1] - gtalk_s[1])
            self.performance_results['ctime_chrome'] = \
                pgutil.get_cpu_usage(SLEEP_DURATION, chrome_e[0] - chrome_s[0])
            self.performance_results['stime_chrome'] = \
                pgutil.get_cpu_usage(SLEEP_DURATION, chrome_e[1] - chrome_s[1])

            # Verify log
            self.run_verification()
        finally:
            pgutil.cleanup_playground(self.playground, True)

        # Report perf
        self.write_perf_keyval(self.performance_results)
