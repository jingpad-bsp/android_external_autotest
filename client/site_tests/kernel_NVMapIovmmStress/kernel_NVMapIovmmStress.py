# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import test

class kernel_NVMapIovmmStress(test.test):
    version = 1
    preserve_srcdir = True

    def run_once(self, options='' ):
        dep = 'nvmap_iovmm'
        dep_dir = os.path.join(self.autodir, 'deps', dep)
        self.job.install_pkg(dep, 'dep', dep_dir)

        exedir = os.path.join(self.autodir, 'deps', 'nvmap_iovmm')

        cmd = '%s/runTest.sh %s %s' % (exedir, exedir, options)

        # If UI is running, we must stop it and restore later.
        status_output = utils.system_output('initctl status ui')
        # If chrome is running, result will be similar to:
        #   ui start/running, process 11895
        logging.info('initctl status ui returns: %s', status_output)
        need_restart_ui = status_output.startswith('ui start')

        # If UI is just stopped or if there's no known X session, we have to
        # start a new one. For factory test, it provides X (DISPLAY) so we can
        # reuse it.
        if need_restart_ui or (not os.getenv('DISPLAY')):
            cmd = 'X :0 & sleep 1; DISPLAY=:0 %s; kill $!' % cmd

        if need_restart_ui:
            utils.system('initctl stop ui', ignore_status=True)

        try:
            summary = utils.system_output(cmd, retain_output=True)
        finally:
            if need_restart_ui:
                utils.system('initctl start ui')

        errors =  'FAIL' in summary
        run_through = 'SUCCESS' in summary
        if errors or (not run_through):
            raise error.TestFail('Test Failed')


