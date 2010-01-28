# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, utils
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class system_AutoLogin(test.test):
    version = 1

    def setup(self):
        self.job.setup_dep(['autox'])
        # create a empty srcdir to prevent the error that checks .version file
        if not os.path.exists(self.srcdir):
            os.mkdir(self.srcdir)

    def run_once(self):
        # Test account information embedded into json file

        dep = 'autox'
        dep_dir = os.path.join(self.autodir, 'deps', dep)
        self.job.install_pkg(dep, 'dep', dep_dir)

        # Set up environment to access login manager
        environment_vars = \
            'DISPLAY=:0.0 XAUTHORITY=/home/chronos/.Xauthority'

        autox_binary = '%s/%s' % (dep_dir, 'usr/bin/autox')
        autox_script = os.path.join(self.bindir, 'autox_script.json')

        try:
            utils.system('%s %s %s' \
                         % (environment_vars, autox_binary, autox_script))
        except error.CmdError, e:
            logging.debug(e)
            raise error.TestFail('AutoX program failed to login for test user')
