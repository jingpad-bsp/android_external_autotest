# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error


class hardware_RamFio(test.test):
    """
    Create ram disk and use FIO to test for ram throughput
    """

    version = 1

    DEFAULT_SIZE = 1024 * 1024 * 1024

    # Region in /proc/meminfo that usable
    USABLE_MEM = ['MemFree:', 'Buffers:', 'Cached:']

    def get_usable_memory(self):
        size = 0
        with open('/proc/meminfo', 'r') as f:
                for lines in f.readlines():
                    items = lines.split()
                    if items[0] in self.USABLE_MEM:
                        size += int(items[1])
        # meminfo report in KB unit
        return size * 1024

    def run_once(self, size=DEFAULT_SIZE, requirements=None):
        """
        Call hardware_StorageFio to test on ram drive

        @param requirements: requirement to pass to hardware_StorageFio
        """

        free_mem = self.get_usable_memory()

        # assume 20% overhead with ramfs
        needed_size = size * 1.2
        if free_mem < needed_size:
            raise error.TestFail(str('Not enough memory. Need: %d, Have: %d' %
                           (needed_size, free_mem)))


        utils.run('mkdir -p /tmp/ramdisk')
        utils.run('mount -t ramfs ramfs /tmp/ramdisk')

        self.job.run_test('hardware_StorageFio',
                          dev='/tmp/ramdisk/test_file',
                          size=size,
                          requirements=requirements)

        utils.run('umount /tmp/ramdisk')

