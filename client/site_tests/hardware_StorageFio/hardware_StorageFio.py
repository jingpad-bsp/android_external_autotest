# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re
from fio_parser import fio_job_output

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class hardware_StorageFio(test.test):
    """
    Runs several fio jobs and reports results.

    fio (flexible I/O tester) is an I/O tool for benchmark and stress/hardware
    verification.

    """

    version = 5

    # Version information for the fio parser object.
    _fio_version = '2.1'

    # http://brick.kernel.dk/snaps/
    def setup(self, tarball = 'fio-2.1.tar.bz2'):
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
        utils.make(make='%s %s make' % (var_ldflags, var_cflags))


    def __find_free_root_partition(self):
        """Locate the spare root partition that we didn't boot off"""

        spare_root_map = {
            '3': '5',
            '5': '3',
        }
        rootdev = utils.system_output('rootdev -s')
        spare_root = rootdev[:-1] + spare_root_map[rootdev[-1]]
        self.__filename = spare_root


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
            if device.startswith(utils.system_output('rootdev -s -d')):
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

        # Obtain the device name by stripping the partition number.
        # For example, on x86: sda3 => sda; on ARM: mmcblk1p3 => mmcblk1.
        device = os.path.basename(
            re.sub('(sd[a-z]|mmcblk[0-9]+)p?[0-9]+', '\\1', self.__filename))
        findsys = utils.run('find /sys/devices -name %s' % device)
        device_path = findsys.stdout.rstrip()

        vendor_file = device_path.replace('block/%s' % device, 'vendor')
        model_file = device_path.replace('block/%s' % device, 'model')
        if os.path.exists(vendor_file) and os.path.exists(model_file):
            vendor = utils.read_one_line(vendor_file).strip()
            model = utils.read_one_line(model_file).strip()
            self.__description = vendor + ' ' + model
        else:
            self.__description = ''


    def __parse_fio(self, lines):
        """Parse the terse fio output

        This collects all metrics given by fio and labels them according to unit
        of measurement and test case name.

        """
        # fio version 2.0.8+ outputs all needed information with --minimal
        # Using that instead of the human-readable version, since it's easier
        # to parse.
        # Following is a partial example of the semicolon-delimited output.
        # 3;fio-2.1;quick_write;0;0;0;0;0;0;0;0;0.000000;0.000000;0;0;0.000000;
        # 0.000000;1.000000%=0;5.000000%=0;10.000000%=0;20.000000%=0;
        # ...
        # Refer to the HOWTO file of the fio package for more information.

        results = {}

        # Extract the values from the test.
        for line in lines.splitlines():
            # Put the values from the output into an array.
            values = line.split(';')
            # This check makes sure that we are parsing the actual values
            # instead of the job description or possible blank lines.
            if len(values) <= 128:
                continue
            results.update(fio_job_output(self._fio_version, values))

        return results


    def __RunFio(self, test):
        """
        Runs fio.

        @return fio results.

        """

        os.chdir(self.srcdir)
        vars = 'LD_LIBRARY_PATH="' + self.autodir + '/deps/libaio/lib"'
        os.putenv('FILENAME', self.__filename)
        os.putenv('FILESIZE', str(self.__filesize))
        # running fio with ionice -c 3 so it doesn't lock out other
        # processes from the disk while it is running.
        # If you want to run the fio test for performance purposes,
        # take out the ionice and disable hung process detection:
        # "echo 0 > /proc/sys/kernel/hung_task_timeout_secs"
        # -c 3 = Idle
        # Tried lowest priority for "best effort" but still failed
        ionice = ' ionice -c 3'
        # Using the --minimal flag for easier results parsing
        # Newest fio doesn't omit any information in --minimal
        fio = utils.run(vars + ionice + ' ./fio --minimal "%s"' %
            os.path.join(self.bindir, test))
        logging.debug(fio.stdout)
        return self.__parse_fio(fio.stdout)


    def initialize(self, dev='', filesize=1024*1024*1024):
        if dev in ['', utils.system_output('rootdev -s -d')]:
            self.__find_free_root_partition()
        else:
            # Use the first partition of the external drive
            if dev[5:7] == 'sd':
                self.__filename = dev + '1'
            else:
                self.__filename = dev + 'p1'
        self.__get_file_size()
        self.__get_device_description()

        # Restrict test to use a given file size, default 1GiB
        self.__filesize = min(self.__filesize, filesize)


    def run_once(self, dev='', quicktest=False, requirements=None):
        """
        Runs several fio jobs and reports resutls.

        """

        # TODO(ericli): need to find a general solution to install dep packages
        # when tests are pre-compiled, so setup() is not called from client any
        # more.
        dep = 'libaio'
        dep_dir = os.path.join(self.autodir, 'deps', dep)
        self.job.install_pkg(dep, 'dep', dep_dir)

        if requirements is not None:
            pass
        elif quicktest:
            requirements = [ 'quick_write', 'quick_read' ]
        elif dev in ['', utils.system_output('rootdev -s -d')]:
            requirements = [
                'surfing',
                'boot',
                'login',
                'seq_read',
                'seq_write',
                '16k_read',
                '16k_write',
                '8k_read',
                '8k_write',
                '4k_read',
                '4k_write'
            ]
        else:
            # TODO(waihong@): Add more test cases for external storage
            requirements = [
                'seq_read',
                'seq_write',
                '16k_read',
                '16k_write',
                '8k_read',
                '8k_write',
                '4k_read',
                '4k_write'
            ]

        results = {}
        for test in requirements:
            # Keys are labeled according to the test case name, which is
            # unique per run, so they cannot clash
            results.update(self.__RunFio(test))

        # Output keys relevent to the performance, larger filesize will run
        # slower, and sda5 should be slightly slower than sda3 on a rotational
        # disk
        self.write_test_keyval({'filesize': self.__filesize,
                                'filename': self.__filename,
                                'device': self.__description})
        logging.info('Device Description: %s', self.__description)
        self.write_perf_keyval(results)
