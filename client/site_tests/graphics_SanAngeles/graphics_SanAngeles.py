# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re

from autotest_lib.client.bin import site_login, site_ui_test
from autotest_lib.client.common_lib import error, site_ui, utils

class graphics_SanAngeles(site_ui_test.UITest):
    version = 1
    preserve_srcdir = True


    def setup(self):
        os.chdir(self.srcdir)
        utils.system('make clean')
        utils.system('make all')


    def run_once(self):
        cmd_gl = os.path.join(self.srcdir, 'SanOGL')
        cmd_gles = os.path.join(self.srcdir, 'SanOGLES')
        cmd_gles_s = os.path.join(self.srcdir, 'SanOGLES_S')
        if os.path.isfile(cmd_gl):
            cmd = cmd_gl
        elif os.path.isfile(cmd_gles):
            cmd = cmd_gles
        elif os.path.isfile(cmd_gles_s):
            cmd = cmd_gles_s
        else:
            raise error.TestFail('Fail to locate SanAngles Observation exe.'
                                 'Test setup error.') 

        cmd = site_ui.xcommand(cmd)
        result = utils.run(cmd, ignore_status = True)

        report = re.findall(r"frame_rate = ([0-9.]+)", result.stdout)
        if len(result.stderr) > 0 or not report:
            raise error.TestFail('Fail to complete San Angeles Observation' +
                                 result.stderr)
        frame_rate = float(report[0])
        logging.info('frame_rate = %.1f' % frame_rate)
        self.write_perf_keyval(
            {'frames_per_sec_rate_san_angeles': frame_rate})
