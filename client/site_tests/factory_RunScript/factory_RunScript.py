# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Runs a script, and passes if the script succeeds.

import logging
import subprocess

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class factory_RunScript(test.test):
    version = 1

    def run_once(self, cmdline):
        if type(cmdline) == list:
            cmdline = '\n'.join(cmdline)

        logging.info('Running script: %s', cmdline)
        process = subprocess.Popen(
            cmdline, shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, _ = process.communicate()
        logging.info('Script output: %s', stdout)
        logging.info('Script return code: %s', process.returncode)
        if process.returncode != 0:
            raise error.TestError('Script failed with return code %s' %
                                  process.returncode)
