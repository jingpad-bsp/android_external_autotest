# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.cros import pyauto_test


class desktopui_ServoPyAuto(pyauto_test.PyAutoTest):
    """Empty client Autotest to pull in the PyAuto dependency."""
    version = 1


    def run_once(self):
        pass
