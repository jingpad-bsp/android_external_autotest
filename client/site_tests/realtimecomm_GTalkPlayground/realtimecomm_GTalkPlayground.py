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
    playground = '/home/chronos/playground'
    dep = 'realtimecomm_playground'

    def setup(self):
        self.job.setup_dep(['realtimecomm_playground'])

    def run_cleanup(self, testdone=False):
        utils.run('pkill chrome', ignore_status=True)
        time.sleep(10)
        utils.run('pkill GoogleTalkPlugin', ignore_status=True)
        time.sleep(10)
        utils.run('rm -f /tmp/tmp.log', ignore_status=True)
        if testdone:
            utils.run('rm -rf %s' % self.playground)
        # Delete previous browser state if any
        shutil.rmtree('/home/chronos/.config/chromium', ignore_errors=True)
        shutil.rmtree('/home/chronos/.config/google-chrome', ignore_errors=True)


    def run_setup(self):
        if os.path.exists(self.playground):
            shutil.rmtree(self.playground)
        shutil.copytree(os.path.join(self.dep_dir, 'src'), self.playground)
        utils.run('chown chronos %s -R' % self.playground)
        src_opt = os.path.join(self.bindir, 'options')
        des_path= '/home/chronos/.Google/'
        opt_path= os.path.join(des_path, 'Google Talk Plugin')
        des_opt = os.path.join(opt_path, 'options')
        utils.run('mkdir -p \'%s\'' % opt_path)
        utils.run('cp -f %s \'%s\'' % (src_opt, des_opt))
        utils.run('chown chronos \'%s\' -R' % des_path)
        utils.run('chmod o+r+w \'%s\'' % des_opt)


    def run_verification(self):
        # TODO(zhurun): Add more checking and perf data collection.
        if not os.path.exists('/tmp/tmp.log'):
            raise error.TestFail('GTalk log file not exist!')
        try:
            log = open(r'/tmp/tmp.log')
            try:
                content = log.read()
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
            finally:
                log.close()
        except IOError:
            raise error.TestFail('Error in reading GTalk log file!')


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
        self.run_cleanup()
        self.run_setup()

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
        time.sleep(SLEEP_DURATION)
        gtalk_e = pgutil.get_utime_stime(pgutil.get_pids('GoogleTalkPlugin'))
        chrome_e = pgutil.get_utime_stime(pgutil.get_pids('chrome/chrome'))

        self.performance_results['ctime_gtalk'] = \
            pgutil.get_cpu_usage(SLEEP_DURATION, gtalk_e[0] - gtalk_s[0])
        self.performance_results['stime_gtalk'] = \
            pgutil.get_cpu_usage(SLEEP_DURATION, gtalk_e[1] - gtalk_s[1])
        self.performance_results['ctime_chrome'] = \
            pgutil.get_cpu_usage(SLEEP_DURATION, chrome_e[0] - chrome_s[0])
        self.performance_results['stime_chrome'] = \
            pgutil.get_cpu_usage(SLEEP_DURATION, chrome_e[1] - chrome_s[1])

        # Verify log
        try:
            self.run_verification()
        finally:
            self.run_cleanup(True)

        # Report perf
        self.write_perf_keyval(self.performance_results)

