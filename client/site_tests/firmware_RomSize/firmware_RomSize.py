# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class firmware_RomSize(test.test):
    version = 1

    def run_once(self):
        cmd = 'dmidecode | grep "ROM Size" | sed "s/.*: \([0-9]\+\) kB/\\1/"'
        size = int(utils.system_output(cmd).strip())
        self.write_perf_keyval({"kb_system_rom_size": size})
