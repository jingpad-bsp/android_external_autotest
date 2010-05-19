# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class hardware_SAT(test.test):
    version = 1

    # http://code.google.com/p/stressapptest/ 
    def setup(self, tarball='stressapptest-1.0.3_autoconf.tar.gz'):
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
        # ./configure stores relevant path and environment variables.
        utils.configure(configure=var_flags + ' ./configure')
        utils.system('make -j %d' % utils.count_cpus())


    def run_once(self, seconds=60):
        # Allow shmem access to all of memory. This is used for 32 bit
        # access to > 1.4G. Virtual address space limitation prevents
        # directly mapping the memory.
        utils.run('mount -o remount,size=100% /dev/shm')
        cpus = max(utils.count_cpus(), 1)
        mbytes = max(int(utils.freememtotal() * .95 / 1024), 512)
        # SAT should use as much memory as possible, while still
        # avoiding OOMs and allowing the kernel to run, so that
        # the maximum amoun tof memory can be tested.
        args = ' -M %d' % mbytes  # megabytes to test
        # The number of seconds under test can be chosen to fit into
        # manufacturing or test flow. 60 seconds gives several
        # passes and several patterns over each memory location
        # and should catch clearly fautly memeory. 4 hours
        # is an effective runin test, to catch lower frequency errors.
        args += ' -s %d' % seconds  # seconds to run
        # One memory copy thread per CPU should keep the memory bus
        # as saturated as possible, while keeping each CPU busy as well.
        args += ' -m %d' % cpus  # memory copy threads.
        # SSE copy and checksum increases the rate at which the CPUs
        # can drive memory, as well as stressing the CPU.
        args += ' -W'  # Use SSE optimizatin in memory threads.
        # File IO threads allow stressful transactions over the
        # south bridge and SATA, as well as potentially finding SSD
        # or disk cache problems. Two threads ensure multiple
        # outstanding transactions to the disk, if supported.
        args += ' -f sat.diskthread.a'  # disk thread
        args += ' -f sat.diskthread.b'

        os.chdir(os.path.join(self.srcdir, 'src'))
        sat = utils.run('./stressapptest' + args)
        logging.debug(sat.stdout)
        if not re.search('Status: PASS', sat.stdout):
            raise error.TestFail(sat.stdout)
