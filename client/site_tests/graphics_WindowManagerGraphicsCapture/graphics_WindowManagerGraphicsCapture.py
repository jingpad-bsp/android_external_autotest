# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re

import os, time
from autotest_lib.client.bin import site_login, test
from autotest_lib.client.common_lib import error, utils

class graphics_WindowManagerGraphicsCapture(test.test):
    version = 1

    def setup(self):
#        site_login.setup_autox(self)
        self.job.setup_dep(['glbench'])

    def run_once(self, script = 'autox_script.json', is_control = False):
#        logged_in = site_login.logged_in()
#        logging.info('was logged in already: %s' % logged_in)

#        if not logged_in:
#            # Test account information embedded into json file.
#            if not site_login.attempt_login(self, script):
#                raise error.TestFail('Could not login')
#
#        # Wait until login complete and window manager is up
#        time.sleep(10)

        #
        # Run glbench
        #
        dep = 'glbench'
        dep_dir = os.path.join(self.autodir, 'deps', dep)
        self.job.install_pkg(dep, 'dep', dep_dir)
  
        exefile = os.path.join(self.autodir, 'deps/glbench/windowmanagertest')
        
        # Enable running in window manager
        exefile = ('chvt 1 && DISPLAY=:0 XAUTHORITY=/home/chronos/.Xauthority ' 
                   + exefile)

        options = "--seconds_to_run 10"
        cmd = "%s %s" % (exefile, options)
        logging.info("command launched: %s" % cmd)
        self.results = utils.system_output(cmd, retain_output=True)
  
#        # If we started logged out, log back out.
#        if not logged_in:
#            site_login.attempt_logout()
