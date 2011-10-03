# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob
import logging
import os
import re
import tempfile

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class security_Minijail0(test.test):
    version = 1

    def get_test_option(self, handle, name):
        setup = ''
        for l in handle.readlines():
            m = re.match('^# %s: (.*)' % name, l.strip())
            if m:
                setup = m.group(1)
        return setup

    def run_test(self, path):
        # Tests are shell scripts with a magic comment line of the form '# args:
        # <stuff>' in them. The <stuff> is substituted in here as minijail0
        # arguments. They can also optionally contain a magic comment of the
        # form '# setup: <stuff>', in which case <stuff> is executed as a shell
        # command before running the test.
        #
        # If '%T' is present in either of the above magic comments, a temporary
        # directory is created, and its name is substituted for '%T' in both of
        # them.
        args = self.get_test_option(file(path), 'args')
        setup = self.get_test_option(file(path), 'setup')
        td = None
        if setup:
            if '%T' in setup:
                td = tempfile.mkdtemp()
                setup = setup.replace('%T', td)
            os.system(setup)
        if '%T' in args:
            td = td or tempfile.mkdtemp()
            args = args.replace('%T', td)

        ret = os.system('/sbin/minijail0 %s /bin/bash %s' % (args, path))
        if td:
            # The test better not have polluted our mount namespace :).
            shutil.rmtree(td)
        return ret

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
