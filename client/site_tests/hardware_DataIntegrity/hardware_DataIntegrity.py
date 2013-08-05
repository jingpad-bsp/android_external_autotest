# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class hardware_DataIntegrity(test.test):
    """
    Performs data integrity test on unmounted partition.

    """

    version = 1


    def setup(self):
        # Rebuild data integrity utility.
        os.chdir(self.srcdir)
        utils.make('clean')
        utils.make('build')


    def _get_partition(self):
        """
        Gets the spare root partition from which the system did not boot.

        On startup, the bootloader selects one of two paritions that contain
        the most up-to-date copy of the ChromeOS kernel. This method determines
        which partition is not currently used.

        This is modified code from platform_CorruptRootfs.

        @return (dev, part) where dev is device and part is the partition.

        """

        rootdev = utils.system_output('rootdev -s')
        logging.info('Root partition being used: %s', rootdev)
        rootdev = rootdev.strip()

        if rootdev == '/dev/sda3':
            dev = '/dev/sda'
            part = '5'
        elif rootdev == '/dev/sda5':
            dev = '/dev/sda'
            part = '3'
        elif rootdev == '/dev/mmcblk0p3':
            dev = '/dev/mmcblk0'
            part = 'p5'
        elif rootdev == '/dev/mmcblk0p5':
            dev = '/dev/mmcblk0'
            part = 'p3'
        else:
            raise TestError('Unexpected root device %s', rootdev)

        return dev, part


    def _run_utility(self, options):
        """
        Runs data integrity utility with parameters.

        @param params: options passed to data integrity utility in string
                       format.

        @returns the output from the utility.

        """

        dev, part = self._get_partition()
        argv = './datint ' + options + ' ' + dev + part
        os.chdir(self.srcdir)
        return utils.system_output(argv)


    def run_once(self, options='-e 10'):
        """
        Executes the test and logs the output.

        """

        # Run data integrity utility and catch output.
        output = self._run_utility(options)

        # Log output.
        output = output.split('\n')
        for line in output:
            logging.info('%s', line)

        # Print statistics.
        results = output[-2].split()
        for stat in results:
            m = re.match(r"(\w+)=(\w+)", stat)
            self.write_perf_keyval({m.group(1) : m.group(2)})

        # Determine pass/fail.
        result = results[3]
        failures = re.match(r"(\w+)=(\w+)", result).group(2)
        if int(failures) != 0:
            raise error.TestFail('One or more corrupted blocks found')
