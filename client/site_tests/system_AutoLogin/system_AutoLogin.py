# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, utils
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class system_AutoLogin(test.test):
    version = 1

    def run_once(self):
        # Test account information embedded into json file        
        
        # Set up environment to access login manager
        environment_cmd = \
            'export DISPLAY=:0.0 && export XAUTHORITY=/home/chronos/.Xauthority'        
                
        xtest_binary = '/usr/bin/autox'
        xtest_script = os.path.join(self.bindir, 'autox_script.json')                            
        
        try:
            utils.system('%s && %s %s' \
                         % (environment_cmd, xtest_binary, xtest_script))
        except error.CmdError, e:
            logging.debug(e)
            raise error.TestFail('AutoX program failed to login for test user')