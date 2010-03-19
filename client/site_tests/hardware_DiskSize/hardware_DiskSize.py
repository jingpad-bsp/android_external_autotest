# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class hardware_DiskSize(test.test):
    version = 1

    def run_once(self):
        cmdline = file('/proc/cmdline').read()
        match = re.search(r'root=/dev/([^ ]+)', cmdline)
        if not match:
            raise error.TestError('Unable to find the root partition')
        device = match.group(1)[:-1]

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

        if gb < 8.0:
            raise error.TestFail("Main disk size < 8G");
