# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import utils
from autotest_lib.client.bin import test

class desktopui_ChromeRunning(test.test):
    version = 1

    def run_once(self):
        utils.system("pgrep '^chrome$'")
