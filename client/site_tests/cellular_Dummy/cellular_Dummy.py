# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.cellular import emulator_config, labconfig

import logging

class cellular_Dummy(test.test):
    version = 1

    def run_once(self, config, technology):
        _, _ = emulator_config.GetDefaultBasestation(config, technology)
