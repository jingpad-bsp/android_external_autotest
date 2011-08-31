# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test


class firmware_FAFTClient(test.test):
    """Empty client Autotest to pull in the FAFT dependency."""
    version = 1


    def run_once(self):
        pass
