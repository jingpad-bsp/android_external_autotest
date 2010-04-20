# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, re, shutil, sys, time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error, site_ui

WARMUP_TIME = 60
SLEEP_DURATION = 260

class realtimecomm_GTalkPlayground(test.test):
    version = 1
    playground = '/home/autotest/playground'
    dep = 'realtimecomm_playground'

    def setup(self):
        self.job.setup_dep([self.dep])


    def run_verification(self):
        # TODO(zhurun): Add more checking and perf data collection.
        if not os.path.exists('/tmp/tmp.log'):
            raise error.TestFail('GTalk log file not exist!')
        content = utils.read_file('/tmp/tmp.log')
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
        # framerate reports for 2 streams.
        # Ignore the first and last framerate since they are not accurate.
        l = re.findall(r"Rendered framerate \((.*)\): (\d+\.?\d*) fps", log)
        if len(l) < 57:
            raise error.TestFail('Error in Video duration!')
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
        para = 'callType=v'
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
        chrome_s = pgutil.get_utime_stime(pgutil.get_pids('chrome/chrome'))
        pulse_s = pgutil.get_utime_stime(pgutil.get_pids('pulseaudio'))
        time.sleep(SLEEP_DURATION)
        gtalk_e = pgutil.get_utime_stime(pgutil.get_pids('GoogleTalkPlugin'))
        chrome_e = pgutil.get_utime_stime(pgutil.get_pids('chrome/chrome'))
        pulse_e = pgutil.get_utime_stime(pgutil.get_pids('pulseaudio'))

        self.performance_results['ctime_gtalk'] = \
            pgutil.get_cpu_usage(SLEEP_DURATION, gtalk_e[0] - gtalk_s[0])
        self.performance_results['stime_gtalk'] = \
            pgutil.get_cpu_usage(SLEEP_DURATION, gtalk_e[1] - gtalk_s[1])
        self.performance_results['ctime_chrome'] = \
            pgutil.get_cpu_usage(SLEEP_DURATION, chrome_e[0] - chrome_s[0])
        self.performance_results['stime_chrome'] = \
            pgutil.get_cpu_usage(SLEEP_DURATION, chrome_e[1] - chrome_s[1])
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
