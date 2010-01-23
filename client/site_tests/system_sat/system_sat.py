# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, re, os, shutil

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class system_sat(test.test):
    version = 1

    # http://stressapptest.googlecode.com/files/\
    #   stressapptest-1.0.1_autoconf.tar.gz
    def setup(self, tarball = 'stressapptest-1.0.1_autoconf.tar.gz'):
        # clean
        if os.path.exists(self.srcdir):
            utils.system('rm -rf %s' % self.srcdir)

        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)

        os.chdir(self.srcdir)
        utils.system('./configure --target=i686-linux-gnu')
        utils.system('make')


    def run_once(self):
        os.chdir(os.path.join(self.srcdir, 'src'))
        cpus = max(utils.count_cpus(), 1)
        sat = utils.run('./stressapptest -v 20 -i %d -C %d -v 20' %
                        (cpus, cpus))
        logging.debug(sat.stdout)
        if not re.search('Status: PASS', sat.stdout):
            raise error.TestFail(sat.stdout)
