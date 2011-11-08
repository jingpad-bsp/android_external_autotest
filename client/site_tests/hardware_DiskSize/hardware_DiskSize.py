# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class hardware_DiskSize(test.test):
    version = 1

    def run_once(self):
        devnode = utils.system_output('rootdev -s -d -i')
        device = os.path.basename(devnode)

        for line in file('/proc/partitions'):
            try:
                major, minor, blocks, name = re.split(r' +', line.strip())
            except ValueError:
                continue
            # TODO(waihong@): Check if this works on ARM.
            if name == device:
                blocks = int(blocks)
                break
        else:
            raise error.TestError('Unable to determine main disk size')

        # Capacity of a hard disk is quoted with SI prefixes, incrementing by
        # powers of 1000, instead of powers of 1024.
        gb = blocks * 1024.0 / 1000.0 / 1000.0 / 1000.0
        self.write_perf_keyval({"gb_main_disk_size": gb})
        logging.info("DiskSize: %.3f GB" % gb)
        min_gb = 16
        if (gb < min_gb):
            raise error.TestError("DiskSize %.3f GB below minimum (%.3f GB)" \
                % (gb, min_gb))

