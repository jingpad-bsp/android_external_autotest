# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class hardware_MemoryTotalSize(test.test):
    version = 1

    def run_once(self):
        # TODO(zmo@): this may not get total physical memory size on ARM
        #             or some x86 machines.
        mem_size = utils.memtotal()
        gb = mem_size / 1024.0 / 1024.0
        self.write_perf_keyval({"gb_memory_total": gb})
        logging.info("MemTotal: %.3f GB" % gb)

        # We intend to check if a machine has at least 1G memory.  However,
        # taking into consideration that some machines reserve certain amount
        # of memory and these won't show in '/proc/meminfo', we lower the
        # threshold to 0.75 Gb.  Hopefully the reserved memory size is less
        # than 256 Mb.
        if gb <= 0.75:
            raise error.TestFail("total system memory size < 1G");
