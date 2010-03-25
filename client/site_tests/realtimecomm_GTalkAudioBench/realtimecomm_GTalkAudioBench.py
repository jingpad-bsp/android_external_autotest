# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, shutil
from autotest_lib.client.bin import test, utils

class realtimecomm_GTalkAudioBench(test.test):
    version = 1
    performance_results = {}
    codecs = [
        'IPCMWB',
        'ISAC',
        'ISACLC',
        'EG711U',
        'EG711A',
        'PCMU',
        'PCMA',
        'iLBC',
        'G722',
        'GSM',
        'speex',
#       'red',
#       'telephone-event',
#       'CN',
    ]
    # TODO(zhurunz): Support ARM once available.
    gips_path = '/home/chronos/gips'
    gips = os.path.join(gips_path, 'audiotesttool.i686')

    def run_once(self):
        # Setup as appropriate
        shutil.rmtree(self.gips_path, ignore_errors=True)
        shutil.copytree(self.bindir, self.gips_path)
        utils.run('chown chronos %s -R' % self.gips_path)

        # Run all codecs
        for codec in self.codecs:
            self.__run_one_codec(codec.lower())

        # Report perf
        self.write_perf_keyval(self.performance_results)


    def __run_one_codec(self, codec):
        # Encode
        para = "--codec=%s encode source.wav output.rtp" % codec
        cmd = "cd %s && su chronos -c '%s %s'" % \
            (self.gips_path, self.gips, para)
        utils.run(cmd)
        cpu_usage, stdout = utils.get_cpu_percentage(
            utils.system_output, cmd, retain_output=True)
        self.performance_results['utime_gtalk_%s_enc' % codec] = cpu_usage

        # Decode
        para = "--codec=%s decode output.rtp output.wav" % codec
        cmd = "cd %s && su chronos -c '%s %s'" % \
            (self.gips_path, self.gips, para)
        utils.run(cmd)
        cpu_usage, stdout = utils.get_cpu_percentage(
            utils.system_output, cmd, retain_output=True)
        self.performance_results['utime_gtalk_%s_dec' % codec] = cpu_usage

