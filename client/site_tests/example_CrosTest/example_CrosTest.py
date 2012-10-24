# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os
from autotest_lib.client.bin import test


class example_CrosTest(test.test):
    """Example Autotest test that pulls in a client dependency.

    All autotest tests must be a decendent of test.test. Other requirements:
    the class name must match the python module's name exactly i.e.
    example_CrosTest is in example_CrosTest.py. If you do not do this, autotest
    will have trouble finding your test module.
    """
    _DEP = 'example_cros_dep'
    version = 1


    def setup(self):
        # Required to ensure your dependency is set up. This is run as part of
        # "building" the test rather than as part of running the test. You
        # should never call setup_dep from run_once or initialize.
        self.job.setup_dep([self._DEP])


    def run_once(self):
        # Install the dependency into the current test's running directory.
        dep = self._DEP
        dep_dir = os.path.join(self.autodir, 'deps', dep)
        self.job.install_pkg(dep, 'dep', dep_dir)

        # Utilize the newly installed pkg by logging its contents.
        src_dir = os.path.join(dep_dir, 'src')
        logging.info('Directory listing of dependency: %r',
                     os.listdir(src_dir))
