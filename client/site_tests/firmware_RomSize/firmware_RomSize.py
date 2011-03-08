# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import flashrom_util

class firmware_RomSize(test.test):
    version = 3

    def run_once(self):
        flashrom = flashrom_util.flashrom_util()

        flashrom.select_bios_flashrom()
        bios_size = flashrom.get_size() / 1024

        flashrom.select_ec_flashrom()
        ec_size = flashrom.get_size() / 1024

        # Always restore system flashrom selection to BIOS.
        flashrom.select_bios_flashrom()

        self.write_perf_keyval({"kb_system_rom_size": bios_size,
                                "kb_ec_rom_size": ec_size})
