# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, re, shutil, time, 

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error, site_ui

WARMUP_TIME = 60
SLEEP_DURATION = 240

def get_pids(program_name):
    """
    Collect a list of pids for all the instances of a program.

    @param program_name the name of the program
    @return list of pids
    """
    return utils.system_output("pidof %s" % program_name).split(" ")


def get_number_of_logical_cpu():
    """
    From /proc/stat/.

    @return number of logic cpu
    """
    ret = utils.system_output("cat /proc/stat | grep ^cpu[0-9+] | wc -l")
    return int(ret)


def get_utime_stime(pids):
    """
    Snapshot the sum of utime and the sum of stime for a list of processes.

    @param pids a list of pid
    @return [sum_of_utime, sum_of_stime]
    """
    timelist = [0, 0]
    for p in pids:
        statFile = file("/proc/%s/stat" % p, "r")
        T = statFile.readline().split(" ")[13:15]
        statFile.close()
        for i in range(len(timelist)):
            timelist[i] = timelist[i] + int(T[i])
    return timelist


def get_cpu_usage(duration, time):
    """
    Calculate cpu usage based on duration and time on cpu.

    @param duration
    @param time on cpu
    @return cpu usage
    """
    return float(time) / float(duration * get_number_of_logical_cpu())


class realtimecomm_GTalkPlayground(test.test):
    version = 1
    playground = '/home/chronos/playground'

    # The tarball is created from GTalk Playground.
    # https://sites.google.com/a/google.com/wavelet/Home/video-playground
    def setup(self, tarball='GTalkPlayground.tar.gz'):
        if os.path.exists(self.playground):
            utils.system('rm -rf %s' % self.playground)
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)


    def run_cleanup(self):
        utils.run('pkill chrome', ignore_status=True)
        time.sleep(10)
        utils.run('pkill GoogleTalkPlugin', ignore_status=True)
        time.sleep(10)
        utils.run('rm -f /tmp/tmp.log', ignore_status=True)
        utils.run('rm -rf %s' % self.playground)
        # Delete previous browser state if any
        shutil.rmtree('/home/chronos/.config/chromium', ignore_errors=True)


    def run_setup(self):
        utils.run('cp -r %s %s' % (self.srcdir, self.playground))
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
        l = re.findall(r"Decoded framerate \((.*)\): (\d+\.?\d*) fps", log)
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


    def run_once(self):
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
        gtalk_s = get_utime_stime(get_pids('GoogleTalkPlugin'))
        chrome_s = get_utime_stime(get_pids('chrome/chrome'))
        time.sleep(SLEEP_DURATION)
        gtalk_e = get_utime_stime(get_pids('GoogleTalkPlugin'))
        chrome_e = get_utime_stime(get_pids('chrome/chrome'))

        self.performance_results['ctime_gtalk'] = \
            get_cpu_usage(SLEEP_DURATION, gtalk_e[0] - gtalk_s[0])
        self.performance_results['stime_gtalk'] = \
            get_cpu_usage(SLEEP_DURATION, gtalk_e[1] - gtalk_s[1])
        self.performance_results['ctime_chrome'] = \
            get_cpu_usage(SLEEP_DURATION, chrome_e[0] - chrome_s[0])
        self.performance_results['stime_chrome'] = \
            get_cpu_usage(SLEEP_DURATION, chrome_e[1] - chrome_s[1])

        # Verify log
        try:
            self.run_verification()
        finally:
            self.run_cleanup()

        # Report perf
        self.write_perf_keyval(self.performance_results)

