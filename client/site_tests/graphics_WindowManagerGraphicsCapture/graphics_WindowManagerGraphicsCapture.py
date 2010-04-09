# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re

import os, time
from autotest_lib.client.bin import site_login, site_ui_test
from autotest_lib.client.common_lib import error, utils

class graphics_WindowManagerGraphicsCapture(site_ui_test.UITest):
    version = 1

    def setup(self):
        self.job.setup_dep(['glbench'])

    def run_once(self, script = 'autox_script.json', is_control = False):
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
