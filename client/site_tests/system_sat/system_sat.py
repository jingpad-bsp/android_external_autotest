# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class system_sat(test.test):
    version = 1

    # http://stressapptest.googlecode.com/files/\
    #   stressapptest-1.0.1_autoconf.tar.gz
    def setup(self, tarball='stressapptest-1.0.1_autoconf.tar.gz'):
        # clean
        if os.path.exists(self.srcdir):
            utils.system('rm -rf %s' % self.srcdir)

        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)

        os.chdir(self.srcdir)
        utils.system('./configure --build=`./config.guess`'
                     ' --host=i686-linux-gnu')
        utils.system('make -j %d' % utils.count_cpus())


    def run_once(self, seconds=60):
        cpus = max(utils.count_cpus(), 1)
        mbytes = max(int(utils.freememtotal() * .95 / 1024), 512)
        args = ' -M %d' % mbytes  # megabytes to test
        args += ' -s %d' % seconds  # seconds to run
        args += ' -m %d' % cpus  # memory copy threads
        args += ' -i %d' % cpus  # memory invert threads
        args += ' -c %d' % cpus  # memory check only threads
        args += ' -C %d' % cpus  # CPU stress threads
        args += ' -n 127.0.0.1 --listen'  # network thread
        args += ' -f diskthread'  # disk thread

        os.chdir(os.path.join(self.srcdir, 'src'))
        sat = utils.run('./stressapptest' + args)
        logging.debug(sat.stdout)
        if not re.search('Status: PASS', sat.stdout):
            raise error.TestFail(sat.stdout)
