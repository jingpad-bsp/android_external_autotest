# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, re, shutil, sys, time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error, site_ui

WARMUP_TIME = 30
SLEEP_DURATION = 90

class realtimecomm_GTalkAudioPlayground(test.test):
    version = 1
    playground = '/home/autotest/playground'
    dep = 'realtimecomm_playground'

    def setup(self):
        self.job.setup_dep([self.dep])


    def run_verification(self):
        if not os.path.exists('/tmp/tmp.log'):
            raise error.TestFail('GTalk log file not exist!')
        content = utils.read_file('/tmp/tmp.log')
        if not "voice state, recv=1 send=1" in content:
            raise error.TestFail('Error in Audio send/recv!')


    def run_once(self):
        self.dep_dir = os.path.join(self.autodir, 'deps', self.dep)
        sys.path.append(self.dep_dir)
        import pgutil

        self.performance_results = {}
        pgutil.cleanup_playground(self.playground)
        pgutil.setup_playground(os.path.join(self.dep_dir, 'src'),
            self.playground, os.path.join(self.bindir, 'options'))

        # Launch Playground
        path = os.path.join(self.playground,
            'buzz/javascript/media/examples')
        page = 'videoplayground.html'
        para = 'callType=a'
        playground_url = "%s/%s?%s" % (path, page, para)
        # Here we somehow have to use utils.run
        # Other approaches like utils.system and site_ui.ChromeSession 
        # cause problem in video.
        # http://code.google.com/p/chromium-os/issues/detail?id=1764
        utils.run('su chronos -c \'DISPLAY=:0 \
            XAUTHORITY=/home/chronos/.Xauthority \
            /opt/google/chrome/chrome \
            --no-first-run %s\' &' % playground_url)

        # Collect ctime,stime for GoogleTalkPlugin
        time.sleep(WARMUP_TIME)
        gtalk_s = pgutil.get_utime_stime(pgutil.get_pids('GoogleTalkPlugin'))
        pulse_s = pgutil.get_utime_stime(pgutil.get_pids('pulseaudio'))
        time.sleep(SLEEP_DURATION)
        gtalk_e = pgutil.get_utime_stime(pgutil.get_pids('GoogleTalkPlugin'))
        pulse_e = pgutil.get_utime_stime(pgutil.get_pids('pulseaudio'))

        self.performance_results['ctime_gtalk'] = \
            pgutil.get_cpu_usage(SLEEP_DURATION, gtalk_e[0] - gtalk_s[0])
        self.performance_results['stime_gtalk'] = \
            pgutil.get_cpu_usage(SLEEP_DURATION, gtalk_e[1] - gtalk_s[1])
        self.performance_results['ctime_pulse'] = \
            pgutil.get_cpu_usage(SLEEP_DURATION, pulse_e[0] - pulse_s[0])
        self.performance_results['stime_pulse'] = \
            pgutil.get_cpu_usage(SLEEP_DURATION, pulse_e[1] - pulse_s[1])

        # Verify log
        try:
            self.run_verification()
        finally:
            pgutil.cleanup_playground(self.playground, True)

        # Report perf
        self.write_perf_keyval(self.performance_results)
