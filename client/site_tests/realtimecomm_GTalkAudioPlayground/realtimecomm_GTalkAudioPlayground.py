# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, re, shutil, sys, time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui, cros_ui_test, httpd

WARMUP_TIME = 30
SLEEP_DURATION = 90
GTALK_LOG_PATH = '/tmp/gtalkplugin.log'

class realtimecomm_GTalkAudioPlayground(cros_ui_test.UITest):
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
        super(realtimecomm_GTalkAudioPlayground, self).initialize(creds=None)

        # Since the DNS redirection is only activated implicitly when the
        # auth service is used, start it up explicitly.
        super(realtimecomm_GTalkAudioPlayground, self).use_local_dns()

    def cleanup(self):
        self._test_server.stop()
        super(realtimecomm_GTalkAudioPlayground, self).cleanup()


    def run_verification(self):
        if not os.path.exists(GTALK_LOG_PATH):
            raise error.TestFail('GTalk log file not exist!')
        content = utils.read_file(GTALK_LOG_PATH)
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
            # Though we are using talk.google.com, this will be redirected
            # to localhost, via DNS redirection
            session = cros_ui.ChromeSession(
                'http://talk.google.com/'
                'buzz/javascript/media/examples/'
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
                pgutil.get_cpu_usage(SLEEP_DURATION, gtalk_e[1] - gtalk_s[1])

            # Verify log
            self.run_verification()
        finally:
            pgutil.cleanup_playground(self.playground, True)

        # Report perf
        self.write_perf_keyval(self.performance_results)
