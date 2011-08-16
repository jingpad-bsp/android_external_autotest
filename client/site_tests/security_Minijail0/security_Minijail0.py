# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob
import logging
import os
import re

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class security_Minijail0(test.test):
    version = 1

    def get_args(self, handle):
        args = ''
        for l in handle.readlines():
            m = re.match('^# args: (.*)', l.strip())
            if m:
                args = m.group(1)
        return args

    def run_test(self, path):
        # Tests are shell scripts with a magic comment line of the form '# args:
        # <stuff>' in them. The <stuff> is substituted in here as minijail0
        # arguments.
        args = self.get_args(file(path))
        return os.system('/sbin/minijail0 %s /bin/bash %s' % (args, path))

    def run_once(self):
        failed = []
        for p in glob.glob('%s/test-*' % self.srcdir):
            name = os.path.basename(p)
            logging.info('Running: %s' % name)
            if self.run_test(p):
                failed.append(name)
        if failed:
            logging.error('Failed: %s' % failed)
            raise error.TestFail('Failed: %s' % failed)
