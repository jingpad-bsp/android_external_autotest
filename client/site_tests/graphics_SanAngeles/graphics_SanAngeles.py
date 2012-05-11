# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui, graphics_ui_test, login

class graphics_SanAngeles(graphics_ui_test.GraphicsUITest):
    version = 2
    preserve_srcdir = True


    def setup(self):
        os.chdir(self.srcdir)
        utils.make('clean')
        utils.make('all')


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
            raise error.TestFail('Failed to locate SanAngeles executable (' +
                                 cmd + '). Test setup error.')

        cmd = cros_ui.xcommand(cmd)
        result = utils.run(cmd, ignore_status = True)

        report = re.findall(r'frame_rate = ([0-9.]+)', result.stdout)
        if not report:
            raise error.TestFail('Could not find frame_rate in stdout (' +
                                 result.stdout + ') ' + result.stderr)

        frame_rate = float(report[0])
        logging.info('frame_rate = %.1f' % frame_rate)
        self.write_perf_keyval(
            {'frames_per_sec_rate_san_angeles': frame_rate})
        if 'error' in result.stderr.lower():
            raise error.TestFail('Error on stderr while running SanAngeles: ' +
                                 result.stderr + ' (' + report[0] + ')')
