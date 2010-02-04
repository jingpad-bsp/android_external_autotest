# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class storage_Fio(test.test):
    version = 3

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
        utils.system('patch -p1 < ../Makefile.patch')
        utils.system('%s %s make' % (var_ldflags, var_cflags))


    def __find_free_root_partition(self):
        """Locate the spare root partition that we didn't boot off"""

        spare_root = {
            '/dev/sda3': '/dev/sda4',
            '/dev/sda4': '/dev/sda3',
        }
        cmdline = file('/proc/cmdline').read()
        match = re.search(r'root=([^ ]+)', cmdline)
        if not match or match.group(1) not in spare_root:
            raise error.TestError('Unable to find a free root partition')
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
            if device[:-1] == 'sda':
                raise error.TestError(
                    'Unable to determine free partitions size')
            else:
                raise error.TestNAError(
                    'Unable to find the partition %s, please plug in a USB '
                    'flash drive and a SD card for testing external storage' %
                    self.__filename)


    def __get_device_description(self):
        """Get the device vendor and model name as its description"""

        # Find the block device in sysfs. For example, a card read device may
        # be in /sys/devices/pci0000:00/0000:00:1d.7/usb1/1-5/1-5:1.0/host4/
        # target4:0:0/4:0:0:0/block/sdb.
        # Then read the vendor and model name in its grand-parent directory.
        device = os.path.basename(self.__filename[:-1])
        findsys = utils.run('find /sys/devices -name %s' % device)
        path = findsys.stdout.rstrip()

        vendor = file(path.replace('block/%s' % device, 'vendor')).read()
        model = file(path.replace('block/%s' % device, 'model')).read()
        self.__description = vendor + ' ' + model


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
        logging.debug(fio.stdout)
        return self.__parse_fio(fio.stdout)


    def initialize(self, dev='/dev/sda'):
        if dev == '/dev/sda':
            self.__find_free_root_partition()
        else:
            self.__filename = dev + '1'
        self.__get_file_size()
        self.__get_device_description()

        # Restrict test to using 1GiB
        self.__filesize = min(self.__filesize, 1024 * 1024 * 1024)


    def run_once(self, dev='/dev/sda'):
        # TODO(ericli): need to find a general solution to install dep packages
        # when tests are pre-compiled, so setup() is not called from client any
        # more.
        dep = 'libaio'
        dep_dir = os.path.join(self.autodir, 'deps', dep)
        self.job.install_pkg(dep, 'dep', dep_dir)

        if dev == '/dev/sda':
            requirements = {
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
        else:
            # TODO(waihong@): Add more test cases for external storage
            requirements = {
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
        for test, metric in requirements.iteritems():
            result = self.__RunFio(test)
            units = metric
            if metric == 'bw':
                units = 'bytes_per_sec'
            results[units + '_' + test] = result[metric]

        # Output keys relevent to the performance, larger filesize will run
        # slower, and sda4 should be slightly slower than sda3 on a rotational
        # disk
        self.write_test_keyval({'filesize': self.__filesize,
                                'filename': self.__filename,
                                'device': self.__description})
        logging.info('Device Description: %s' % self.__description)
        self.write_perf_keyval(results)
