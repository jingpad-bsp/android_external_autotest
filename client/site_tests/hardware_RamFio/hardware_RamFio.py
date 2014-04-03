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

    def run_once(self, size=DEFAULT_SIZE, requirements=None, dry_run=False):
        """
        Call hardware_StorageFio to test on ram drive

        @param size: size to test in byte
                     0 means all usable memory
        @param requirements: requirement to pass to hardware_StorageFio
        """

        # assume 20% overhead with ramfs
        usable_mem = int(utils.usable_memtotal() * 1024 * 0.8)

        if size == 0:
            size = usable_mem
        elif usable_mem < size:
            raise error.TestFail(str('Not enough memory. Want: %d, Usable: %d' %
                           (size, usable_mem)))

        self.write_perf_keyval({'Size' : size})

        if dry_run:
            return

        utils.run('mkdir -p /tmp/ramdisk')
        utils.run('mount -t ramfs ramfs /tmp/ramdisk')

        self.job.run_test('hardware_StorageFio',
                          dev='/tmp/ramdisk/test_file',
                          size=size,
                          requirements=requirements)

        utils.run('umount /tmp/ramdisk')

