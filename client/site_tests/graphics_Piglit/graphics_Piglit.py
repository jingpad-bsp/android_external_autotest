# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""
Runs the piglit OpenGL suite of tests.
"""

import logging, os, re
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui
from autotest_lib.client.cros.graphics import graphics_utils

class graphics_Piglit(test.test):
    """
    Collection of automated tests for OpenGL implementations.
    """
    version = 2
    preserve_srcdir = True
    GSC = None

    def setup(self):
        self.job.setup_dep(['piglit'])

    def initialize(self):
        self.GSC = graphics_utils.GraphicsStateChecker()

    def cleanup(self):
        if self.GSC:
            self.GSC.finalize()

    # hard wiring the cros-driver.test config file until we
    # need to parameterize this test for short/extended testing
    def run_once(self):
        # TODO(ihf): Hook up crash reporting, right now it is doing nothing.
        self.GSC.crash_blacklist.append('glslparsertest')
        self.GSC.crash_blacklist.append('shader_runner')

        # SCBA Sandy Bridge crash cases
        self.GSC.crash_blacklist.append('draw-elements-base-vertex-neg')
        self.GSC.crash_blacklist.append('glsl-fs-raytrace-bug27060')
        self.GSC.crash_blacklist.append('glsl-vs-raytrace-bug26691')
        self.GSC.crash_blacklist.append('fp-long-alu')

        dep = 'piglit'
        dep_dir = os.path.join(self.autodir, 'deps', dep)
        self.job.install_pkg(dep, 'dep', dep_dir)
        # 'results/default/graphics_Piglit/cros-driver')
        log_path = os.path.join(self.outputdir, 'piglit-run.log')
        results_path = os.path.join(self.outputdir, 'cros-driver')
        piglit_path = os.path.join(dep_dir, 'piglit')
        bin_path = os.path.join(piglit_path, 'bin')
        summary = ''
        if not (os.path.exists(os.path.join(piglit_path, 'piglit-run.py')) and
                os.path.exists(bin_path) and
                os.listdir(bin_path)):
            raise error.TestError('piglit not found at %s' % piglit_path)

        os.chdir(piglit_path)
        cmd = 'python piglit-run.py'
        # Piglit by default wants to run multiple tests in separate
        # processes concurrently. Strictly serialize this.
        cmd = cmd + ' --concurrent=0'
        cmd = cmd + ' tests/cros-driver.tests'
        cmd = cmd + ' ' + results_path
        # Output all commands as run sequentially with results in
        # piglit-run.log and store everything for future inspection.
        cmd = cmd + ' | tee ' + log_path
        cmd = cros_ui.xcommand(cmd)
        logging.info('Calling %s', cmd)
        utils.run(cmd,
                  stdout_tee=utils.TEE_TO_LOGS,
                  stderr_tee=utils.TEE_TO_LOGS)
        # count number of pass, fail, warn and skip in the test summary
        summary_path = os.path.join(results_path, 'main')
        f = open(summary_path, 'r')
        summary = f.read()
        f.close()

        if not summary:
            raise error.TestError('Test summary was empty')

        # output numbers for plotting by harness
        keyvals = {}
        for k in ['pass', 'fail', 'crash', 'warn', 'skip']:
            num = len(re.findall(r'"result": "' + k + '",', summary))
            keyvals['count_subtests_' + k] = num
            logging.info('Piglit: %d ' + k, num)
            self.output_perf_value(description=k, value=num,
                                   units='count', higher_is_better=(k=='pass'))

        self.write_perf_keyval(keyvals)

        # generate human friendly html output
        cmd = 'python piglit-summary-html.py'
        cmd = cmd + ' ' + os.path.join(results_path, 'html')
        cmd = cmd + ' ' + results_path
        utils.run(cmd)
