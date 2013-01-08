# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re, struct, sys

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

def memory_channel_args_sandybridge(channel_modules):
    with open('/proc/bus/pci/00/00.0', 'r', 0) as fd:
        fd.seek(0x48)
        mchbar = struct.unpack('=I', fd.read(4))[0]
    if not mchbar & 1:
        raise error.TestError('Host Memory Mapped Register Range not enabled.')
    mchbar &= ~1

    with open('/dev/mem', 'r', 0) as fd:
        fd.seek(mchbar + 0x5000)
        mad_chnl = struct.unpack('=I', fd.read(4))[0]
        fd.seek(mchbar + 0x5024)
        channel_hash = struct.unpack('=I', fd.read(4))[0]

    if (mad_chnl >> 4) & 3 != 2:
        raise error.TestError('This test does not support triple-channel mode.')
    if mad_chnl & 3 == 0 and (mad_chnl >> 2) & 3 == 1:
        channel_order = [0, 1]
    elif mad_chnl & 3 == 1 and (mad_chnl >> 2) & 3 == 0:
        logging.warn('Non-default memory channel configuration... please '
                     'double-check that this is correct and intended.')
        channel_order = [1, 0]
    else:
        raise error.TestError('Invalid channel configuration: %x' % mad_chnl)

    if not channel_hash & (1 << 23):
        logging.warn('Memory channel_hash deactivated... going with cache-line '
                     'sized ping-pong as a wild guess.')
        channel_hash = 1
    channel_hash = (channel_hash & 0x3FFF) << 6

    return (' --memory_channel %s --memory_channel %s --channel_hash 0x%x'
            ' --channel_width 64' % (
                    ','.join(channel_modules[channel_order[0]]),
                    ','.join(channel_modules[channel_order[1]]),
                    channel_hash))


class hardware_SAT(test.test):
    version = 1

    # http://code.google.com/p/stressapptest/
    def setup(self, tarball='stressapptest-1.0.6_autoconf.tar.gz'):
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
        utils.make()


    def run_once(self, seconds=60, free_memory_fraction=0.95):
        '''
        Args:
          free_memory_fraction: Fraction of free memory (as determined by
            utils.freememtotal()) to use.
        '''
        assert free_memory_fraction > 0
        assert free_memory_fraction < 1

        # Allow shmem access to all of memory. This is used for 32 bit
        # access to > 1.4G. Virtual address space limitation prevents
        # directly mapping the memory.
        utils.run('mount -o remount,size=100% /dev/shm')
        cpus = max(utils.count_cpus(), 1)
        mbytes = max(int(utils.freememtotal() * free_memory_fraction / 1024),
                     512)
        # Even though shared memory allows us to go past the 1.4G
        # limit, ftruncate still limits us to 2G max on 32 bit systems.
        if sys.maxsize < 2**32 and mbytes > 2047:
            mbytes = 2047
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

        if utils.get_board() == 'LINK':
            args += memory_channel_args_sandybridge([
                    ['U1', 'U2', 'U3', 'U4'],
                    ['U6', 'U5', 'U7', 'U8']])  # yes, U6 is actually before U5

        os.chdir(os.path.join(self.srcdir, 'src'))
        sat = utils.run('./stressapptest' + args)
        logging.debug(sat.stdout)
        if not re.search('Status: PASS', sat.stdout):
            raise error.TestFail(sat.stdout)
