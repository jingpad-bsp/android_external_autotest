# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""
Runs the piglit OpenGL suite of tests.
"""

import logging, os, re
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui, cros_ui_test

# most graphics tests need the auto_login feature of UITest
class graphics_Piglit(cros_ui_test.UITest):
    version = 1
    preserve_srcdir = True

    def setup(self):
        self.job.setup_dep(['piglit'])

    # hard wiring the cros-driver.test config file until we
    # need to parameterize this test for short/extended testing
    def run_once(self):
        # expected crashes inside of piglit need to be listed for UITest
        self.crash_blacklist.append('attribute0')
        self.crash_blacklist.append('cashewd')
        self.crash_blacklist.append('fbo-depth-sample-compare')
        self.crash_blacklist.append('getuniform-01')
        self.crash_blacklist.append('glsl-bug-22603')
        self.crash_blacklist.append('glsl-fs-color-matrix')
        self.crash_blacklist.append('glsl-fs-discard-02')
        self.crash_blacklist.append('glslparsertest')
        self.crash_blacklist.append('shader_runner')

        dep = 'piglit'
        dep_dir = os.path.join(self.autodir, 'deps', dep)
        self.job.install_pkg(dep, 'dep', dep_dir)
        # 'results/default/graphics_Piglit/cros-driver')
        results_path = os.path.join(self.outputdir, 'cros-driver')
        piglit_path = os.path.join(dep_dir, 'piglit')
        bin_path = os.path.join(piglit_path, 'bin')
        summary = ''
        if (os.path.exists(os.path.join(piglit_path, 'piglit-run.py')) and
            os.path.exists(bin_path) and
            os.listdir(bin_path)):

            os.chdir(piglit_path)
            cmd = 'python piglit-run.py'
            cmd = cmd + ' tests/cros-driver.tests'
            cmd = cmd + ' ' + results_path
            cmd = cros_ui.xcommand(cmd)
            logging.info('Calling %s' % cmd)
            utils.run(cmd)
            # count number of pass, fail, warn and skip in the test summary
            summary_path = os.path.join(results_path, 'summary')
            f = open(summary_path, 'r')
            summary = f.read()
            f.close()
        else:
            return error.TestError('test runs only on x86 (needs OpenGL)')

        # get passed
        report = re.findall(r'\nresult: pass', summary)
        if not report:
            return error.TestFail('Output missing: pass number unknown!')
        passed = len(report)
        # get failed
        report = re.findall(r'\nresult: fail', summary)
        if not report:
            return error.TestFail('Output missing: fail number unknown!')
        failed = len(report)
        # get warned
        report = re.findall(r'\nresult: warn', summary)
        if not report:
            return error.TestFail('Output missing: warn number unknown!')
        warned = len(report)
        # get skipped
        report = re.findall(r'\nresult: skip', summary)
        if not report:
            return error.TestFail('Output missing: skip number unknown!')
        skipped = len(report)

        # doesn't seem to send it to the host console
        logging.info('Piglit: %d pass', passed)
        logging.info('Piglit: %d fail', failed)
        logging.info('Piglit: %d warn', warned)
        logging.info('Piglit: %d skip', skipped)

        # output numbers for plotting by harness
        keyvals = {}
        keyvals['count_subtests_pass'] = passed
        keyvals['count_subtests_fail'] = failed
        keyvals['count_subtests_warn'] = warned
        keyvals['count_subtests_skip'] = skipped
        self.write_perf_keyval(keyvals)

        # generate human friendly html output
        cmd = 'python piglit-summary-html.py'
        cmd = cmd + ' ' + os.path.join(results_path, 'html')
        cmd = cmd + ' ' + results_path
        utils.run(cmd)

