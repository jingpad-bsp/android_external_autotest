# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import stat

from autotest_lib.client.bin import utils, test
from autotest_lib.client.common_lib import error

ROOTFS_SIZE = 2 * 1024 * 1024 * 1024

class platform_PartitionCheck(test.test):
    """
    Verify partition size is correct.
    """
    version = 1

    def get_block_size(self, device):
        """
        Check the block size of a block device.

        Args:
            device: string, name of the block device.
        Returns:
            int, size of block in bytes.
        """

        # Construct a pathname to the various files we care about.
        sysfs_path = os.path.join('/sys', 'block', device, 'queue')
        sector_file = os.path.join(sysfs_path, 'hw_sector_size')
        logical_file = os.path.join(sysfs_path, 'logical_block_size')
        physical_file = os.path.join(sysfs_path, 'physical_block_size')

        sector_size = int(utils.read_one_line(sector_file))
        logical_size = int(utils.read_one_line(logical_file))
        physical_size = int(utils.read_one_line(physical_file))

        self.assert_(logical_size == physical_size, (
            'Warning %s and %s are not equal' % (logical_file, physical_file)))
        self.assert_(sector_size == physical_size, (
            'Warning %s and %s are not equal' % (sector_file, physical_file)))

        return sector_size

    def get_partition_size(self, device, partition):
        """
        Get the number of blocks in the partition.

        Args:
            partition: string, partition name
        Returns:
            int, number of blocks
        """

        part_file = os.path.join('/sys', 'block', device, partition, 'size')
        part_blocks = int(utils.read_one_line(part_file))
        return part_blocks

    def run_once(self):
        errors = 0
        cpu_type = utils.get_cpu_arch()

        if cpu_type == 'arm':
            device = 'mmcblk0'
            partitions = ['mmcblk0p3', 'mmcblk0p5']
        else:
            device = 'sda'
            partitions = ['sda3', 'sda5']

        block_size = self.get_block_size(device)

        for p in partitions:
            pblocks = self.get_partition_size(device, p)
            psize = pblocks * block_size
            if psize != ROOTFS_SIZE:
                logging.warn('%s is %d bytes' % (p, psize))
                errors += 1

        # If self.error is not zero, there were errors.
        if errors > 0:
            raise error.TestFail('There were %d partition errors' % errors)
