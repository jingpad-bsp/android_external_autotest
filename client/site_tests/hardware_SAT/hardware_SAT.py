# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class hardware_SAT(test.test):
    version = 1

    # http://stressapptest.googlecode.com/files/\
    #   stressapptest-1.0.2_autoconf.tar.gz
    def setup(self, tarball='stressapptest-1.0.2_autoconf.tar.gz'):
        # clean
        if os.path.exists(self.srcdir):
            utils.system('rm -rf %s' % self.srcdir)

        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)

        self.job.setup_dep(['libaio'])
        ldflags = '-L' + self.autodir + '/deps/libaio/lib'
        cflags = '-I' + self.autodir + '/deps/libaio/include'
        # Add paths to libaio files.
        var_flags = 'LDFLAGS="' + ldflags + '"'
        var_flags += ' CXXFLAGS="' + cflags + '"'
        var_flags += ' CFLAGS="' + cflags + '"'
        var_flags += ' LIBS="-static -laio"'

        os.chdir(self.srcdir)
        config_params = ''
        if 'CBUILD' in os.environ and 'CHOST' in os.environ:
            config_params = '--build=%s --host=%s' % (os.environ['CBUILD'],
                                                      os.environ['CHOST'])
        # ./configure stores relevant path and environment variables.
        utils.system('%s ./configure %s' % (var_flags, config_params))
        utils.system('make -j %d' % utils.count_cpus())


    def run_once(self, seconds=60):
        cpus = max(utils.count_cpus(), 1)
        mbytes = max(int(utils.freememtotal() * .95 / 1024), 512)
        args = ' -M %d' % mbytes  # megabytes to test
        args += ' -s %d' % seconds  # seconds to run
        args += ' -m %d' % cpus  # memory copy threads
        args += ' -i %d' % cpus  # memory invert threads
        args += ' -C %d' % cpus  # CPU stress threads
        args += ' -f diskthread'  # disk thread

        os.chdir(os.path.join(self.srcdir, 'src'))
        sat = utils.run('./stressapptest' + args)
        logging.debug(sat.stdout)
        if not re.search('Status: PASS', sat.stdout):
            raise error.TestFail(sat.stdout)
