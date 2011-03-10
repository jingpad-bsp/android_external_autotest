# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, re, shutil, sys, time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui, cros_ui_test, httpd

WARMUP_TIME = 30
SLEEP_DURATION = 90

class realtimecomm_GTalkAudioPlayground(cros_ui_test.UITest):
    version = 1
    dep = 'realtimecomm_playground'

    def setup(self):
        self.playground = os.path.join(self.autodir, 'playground')
        self.job.setup_dep([self.dep])


    def initialize(self, creds='$default'):
        self.dep_dir = os.path.join(self.autodir, 'deps', self.dep)

        # Start local HTTP server to serve playground.
        self._test_server = httpd.HTTPListener(
            8001, docroot=os.path.join(self.dep_dir, 'src'))
        self._test_server.run()
        super(realtimecomm_GTalkAudioPlayground, self).initialize(creds)


    def cleanup(self):
        self._test_server.stop()
        super(realtimecomm_GTalkAudioPlayground, self).cleanup()


    def run_verification(self):
        if not os.path.exists('/tmp/tmp.log'):
            raise error.TestFail('GTalk log file not exist!')
        content = utils.read_file('/tmp/tmp.log')
        if not "voice state, recv=1 send=1" in content:
            raise error.TestFail('Error in Audio send/recv!')


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
            session = cros_ui.ChromeSession(
                'http://localhost:8001/buzz/javascript/media/examples/'
                'videoplayground.html?callType=a')

            # Collect ctime,stime for GoogleTalkPlugin
            time.sleep(WARMUP_TIME)
            gtalk_s = pgutil.get_utime_stime(
                pgutil.get_pids('GoogleTalkPlugin'))
            time.sleep(SLEEP_DURATION)
            gtalk_e = pgutil.get_utime_stime(
                pgutil.get_pids('GoogleTalkPlugin'))

            self.performance_results['ctime_gtalk'] = \
                pgutil.get_cpu_usage(SLEEP_DURATION, gtalk_e[0] - gtalk_s[0])
            self.performance_results['stime_gtalk'] = \
                pgutil.get_cpu_usage(SLEEP_DURA, gtalk_e[1] - gtalk_s[1])

            # Verify log
            self.run_verification()
        finally:
            pgutil.cleanup_playground(self.playground, True)

        # Report perf
        self.write_perf_keyval(self.performance_results)
