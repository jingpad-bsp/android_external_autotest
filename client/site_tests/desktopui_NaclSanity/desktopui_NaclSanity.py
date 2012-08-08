# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.cros import chrome_test


class desktopui_NaclSanity(chrome_test.PyAutoFunctionalTest):
    """Sanity test for NaCl.

    Secure shell uses NaCl, so verifying that secure shell
    works is a good sanity for NaCl.
    """
    version = 1


    def run_once(self):
        self.run_pyauto_functional(
            tests=['secure_shell.SecureShellTest.testLaunch'])
