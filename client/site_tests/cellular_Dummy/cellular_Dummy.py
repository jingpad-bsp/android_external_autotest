# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.cros.cellular import cell_tools, emulator_config


class cellular_Dummy(test.test):
    version = 1

    def run_once(self, config, technology):
        _, _ = emulator_config.GetDefaultBasestation(config, technology)
        cell_tools.PrepareModemForTechnology('', technology)
