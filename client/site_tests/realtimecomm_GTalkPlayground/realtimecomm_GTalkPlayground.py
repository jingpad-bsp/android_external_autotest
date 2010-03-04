# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error, site_ui

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
        utils.run('killall chrome', ignore_status=True)
        time.sleep(1)
        utils.run('killall GoogleTalkPlugin', ignore_status=True)
        time.sleep(1)
        utils.run('rm -f /tmp/tmp.log', ignore_status=True)
        utils.run('rm -rf %s' % self.playground)


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
            finally:
                log.close()
        except IOError:
            raise error.TestFail('Error in reading GTalk log file!')


    def run_once(self):
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
        # http://code.google.com/p/chromium-os/issues/detail?id=1764
        utils.run('su chronos -c \'DISPLAY=:0 \
            XAUTHORITY=/home/chronos/.Xauthority \
            /opt/google/chrome/chrome \
            --no-first-run %s\' &' % playground_url)
        time.sleep(120)

        # Verify log
        self.run_verification()
        self.run_cleanup()
