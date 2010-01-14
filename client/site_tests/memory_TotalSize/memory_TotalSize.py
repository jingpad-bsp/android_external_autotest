# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class memory_TotalSize(test.test):
    version = 1

    def run_once(self):
        # TODO(zmo@): this may not get total physical memory size on ARM.
        mem_size = utils.memtotal()
        gb = mem_size / 1024.0 / 1024.0
        self.write_perf_keyval({"gb_memory_total": gb})
        logging.info("MemTotal: %.3f GB" % gb)

        if gb < 1.0:
            raise error.TestFail("total system memory size < 1G");
