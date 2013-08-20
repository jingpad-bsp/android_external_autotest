# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

DEFAULT_MIN_GB = 16
# Allowable amount of bits eMMC vendor can use in firmware to support bad block
# replacement and metadata.
EMMC_VENDOR_ALLOWED_GB = 0.25

class hardware_DiskSize(test.test):
    version = 1

    def _is_emmc(self):
        path = os.path.join("/sys/class/block/", self._device,
                            "device", "type")
        if not os.path.exists(path):
            return False
        return utils.read_one_line(path) == 'MMC'


    def _compute_min_gb(self):
        """Computes minimum size allowed primary storage device.

        TODO(tbroch): Add computation of raw bytes in eMMC using 'Chip Specific
        Data' (CSD & EXT_CSD) defined by JEDEC JESD84-A44.pdf if possible.

        CSD :: /sys/class/block/<device>/device/csd
        EXT_CSD :: debugfs

        Algorithm should look something like this:
        CSD[C_SIZE] = 0xfff == eMMC > 2GB
        EXT_CSD[SEC_COUNT] = # of 512byte sectors

        Now for existing eMMC I've examined I do see the C_SIZE == 0xfff.
        Unfortunately the SEC_COUNT appears to have excluded the sectors
        reserved for metadata & repair.  Perhaps thats by design in which case
        there is no mechanism to determine the actual raw sectors.

        For now I use 0.25GB as an acceptable fudge.

        Returns:
            integer, in GB of minimum storage size.
        """

        min_gb = DEFAULT_MIN_GB
        if self._is_emmc():
            min_gb -= EMMC_VENDOR_ALLOWED_GB
        return min_gb


    def run_once(self):
        devnode = utils.system_output('rootdev -s -d -i')
        self._device = os.path.basename(devnode)

        for line in file('/proc/partitions'):
            try:
                _, _, blocks, name = re.split(r' +', line.strip())
            except ValueError:
                continue
            if name == self._device:
                blocks = int(blocks)
                break
        else:
            raise error.TestError('Unable to determine main disk size')

        # Capacity of a hard disk is quoted with SI prefixes, incrementing by
        # powers of 1000, instead of powers of 1024.
        gb = blocks * 1024.0 / 1000.0 / 1000.0 / 1000.0
        self.write_perf_keyval({"gb_main_disk_size": gb})
        min_gb = self._compute_min_gb()
        logging.info("DiskSize: %.3f GB MinDiskSize: %.3f GB", gb, min_gb)
        if (gb < min_gb):
            raise error.TestError("DiskSize %.3f GB below minimum (%.3f GB)" \
                % (gb, min_gb))

