# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
import os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class storage_Fio(test.test):
    version = 2

    # http://brick.kernel.dk/snaps/fio-1.36.tar.bz2
    def setup(self, tarball = 'fio-1.36.tar.bz2'):
        # clean
        if os.path.exists(self.srcdir):
            utils.system('rm -rf %s' % self.srcdir)

        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)

        self.job.setup_dep(['libaio'])
        ldflags = '-L' + self.autodir + '/deps/libaio/lib'
        cflags = '-I' + self.autodir + '/deps/libaio/include'
        var_ldflags = 'LDFLAGS="' + ldflags + '"'
        var_cflags  = 'CFLAGS="' + cflags + '"'

        os.chdir(self.srcdir)
        utils.system('%s %s make' % (var_ldflags, var_cflags))

    def __find_free_partition(self):
        """Locate the spare root partition that we didn't boot off"""

        spare_root = {
            '/dev/sda3': '/dev/sda4',
            '/dev/sda4': '/dev/sda3',
        }
        cmdline = file('/proc/cmdline').read()
        match = re.search(r'root=([^ ]+)', cmdline)
        if not match or match.group(1) not in spare_root:
            raise error.TestError('Unable to find a free partition to test')
        self.__filename = spare_root[match.group(1)]


    def __get_file_size(self):
        """Return the size in bytes of the device pointed to by __filename"""

        device = os.path.basename(self.__filename)
        for line in file('/proc/partitions'):
            try:
                major, minor, blocks, name = re.split(r' +', line.strip())
            except ValueError:
                continue
            if name == device:
                blocks = int(blocks)
                self.__filesize = 1024 * blocks
                break
        else:
            raise error.TestError('Unable to determine free partitions size')


    def __parse_fio(self, lines):
        """Parse the human readable fio output

        This only collects bandwidth and iops numbers from fio.

        """

        # fio --minimal doesn't output information about the number of ios
        # that occurred, making it unsuitable for this test.  Instead we parse
        # the human readable output with some regular expressions
        read_re = re.compile(r'read :.*bw=([0-9]*K?)B/s.*iops=([0-9]*)')
        write_re = re.compile(r'write:.*bw=([0-9]*K?)B/s.*iops=([0-9]*)')

        results = {}
        for line in lines.split('\n'):
            line = line.rstrip()
            match = read_re.search(line)
            if match:
                results['read_bw'] = match.group(1)
                results['read_iops'] = match.group(2)
                continue
            match = write_re.search(line)
            if match:
                results['write_bw'] = match.group(1)
                results['write_iops'] = match.group(2)
                continue

        # Turn the values into numbers
        for metric, result in results.iteritems():
            if result[-1] == 'K':
                result = int(result[:-1]) * 1024
            else:
                result = int(result)
            results[metric] = result

        results['bw'] = (results.get('read_bw', 0) +
                         results.get('write_bw', 0))
        results['iops'] = (results.get('read_iops', 0) +
                           results.get('write_iops', 0))
        return results


    def __RunFio(self, test):
        os.chdir(self.srcdir)
        vars = 'LD_LIBRARY_PATH="' + self.autodir + '/deps/libaio/lib"'
        os.putenv('FILENAME', self.__filename)
        os.putenv('FILESIZE', str(self.__filesize))
        fio = utils.run(vars + ' ./fio "%s"' % os.path.join(self.bindir, test))
        return self.__parse_fio(fio.stdout)


    def initialize(self):
        self.__find_free_partition()
        self.__get_file_size()

        # Restrict test to using 1GiB
        self.__filesize = min(self.__filesize, 1024 * 1024 * 1024)


    def run_once(self):
        metrics = {
            'surfing': 'iops',
            'boot': 'bw',
            'login': 'bw',
            'seq_read': 'bw',
            'seq_write': 'bw',
            '16k_read': 'iops',
            '16k_write': 'iops',
            '8k_read': 'iops',
            '8k_write': 'iops',
            '4k_read': 'iops',
            '4k_write': 'iops',
        }

        results = {}
        for test, metric in metrics.iteritems():
            result = self.__RunFio(test)
            results[test] = result[metric]

        # Output keys relevent to the performance, larger filesize will run
        # slower, and sda4 should be slightly slower than sda3 on a rotational
        # disk
        self.write_test_keyval({'filesize': self.__filesize,
                                'filename': self.__filename})
        self.write_perf_keyval(results)

