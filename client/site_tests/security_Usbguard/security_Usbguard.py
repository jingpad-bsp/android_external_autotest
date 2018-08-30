# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import time

from autotest_lib.client.bin import test
from autotest_lib.client.cros import upstart


class security_Usbguard(test.test):
    """Tests the usbguard init scripts to make sure the service starts and stops
    as intended.
    """

    version = 2
    RULES_FILE = '/run/usbguard/rules.conf'

    def run_once(self):
        """Runs the security_Usbguard test.
        """

        upstart.emit_event('screen-locked')
        # Give usbguard-daemon time to run out of restart attempts.
        time.sleep(5)

        upstart.ensure_running('usbguard-wrapper')
        upstart.ensure_running('usbguard')
        if not os.path.isfile(self.RULES_FILE):
            raise RuntimeError('"%s" was not generated!' % (self.RULES_FILE,))
        if os.path.getsize(self.RULES_FILE) == 0:
            raise RuntimeError('%s was empty!' % (self.RULES_FILE,))

        upstart.emit_event('screen-unlocked')

        if upstart.is_running('usbguard'):
            raise RuntimeError('usbguard-daemon still running!')
        if upstart.is_running('usbguard-wrapper'):
            raise RuntimeError('usbguard-wrapper cleanup did not execute!')
