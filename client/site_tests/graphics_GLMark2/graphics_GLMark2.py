# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Run the test with validation_mode=True to invoke glmark2 to do quick
# validation that runs in a second. When glmark2 is run in normal mode, it
# outputs a final performance score, and the test checks the performance score
# against minimum requirement if min_score is set.

import logging
import os
import re

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


GLMARK2_SCORE_RE = 'glmark2 Score: (\d+)'

class graphics_GLMark2(test.test):
    version = 1
    preserve_srcdir = True

    def setup(self):
        self.job.setup_dep(['glmark2'])

    def run_once(self, size='800x600', validation_mode=False, min_score=None):
        dep = 'glmark2'
        dep_dir = os.path.join(self.autodir, 'deps', dep)
        self.job.install_pkg(dep, 'dep', dep_dir)
        glmark2 = os.path.join(dep_dir, 'bin/glmark2')
        options = []
        options.append('--size %s' % size)
        if validation_mode:
           options.append('--validate')
        else:
           options.append('--annotate')
        cmd = '%s %s' % (glmark2, ' '.join(options))
        if not os.getenv('DISPLAY'):
            cmd = 'X :1 & sleep 1; DISPLAY=:1 %s; kill $!' % cmd

        if os.environ.get('CROS_FACTORY'):
            from autotest_lib.client.cros.factory import ui
            ui.start_reposition_thread('^glmark')
        result = utils.run(cmd)
        for line in result.stderr.splitlines():
            if line.startswith('Error:'):
                raise error.TestFail(line)

        if not validation_mode:
            score = None
            for line in result.stdout.splitlines():
                # glmark2 output the final performance score as:
                #   glmark2 Score: 530
                match = re.findall(GLMARK2_SCORE_RE, line)
                if match:
                    score = int(match[0])
            if score is None:
                raise error.TestFail('Unable to read benchmark score')
            # Output numbers for plotting by harness.
            logging.info('GLMark2 score: %d', score)
            if os.environ.get('CROS_FACTORY'):
                from autotest_lib.client.cros.factory.event_log import EventLog
                EventLog('graphics_GLMark2').Log('glmark2_score', score=score)
            keyvals = {}
            keyvals['glmark2_score'] = score
            self.write_perf_keyval(keyvals)
            if min_score is not None and score < min_score:
                raise error.TestFail('Benchmark score %d < %d (minimum score '
                                     'requirement)' % (score, min_score))
