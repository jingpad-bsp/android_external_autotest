# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

#pylint: disable-msg=C0111

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import chrome_test


class desktopui_WebRTC(chrome_test.PyAutoFunctionalTest):
    version = 1


    def run_once(self):
        try:
            self.run_pyauto_functional(suite='WEBRTC')
        except Exception as err:
            raise error.TestFailRetry(err)
