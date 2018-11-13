# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros import upstart


class security_Usbguard(test.test):
    """Tests the USBGuard init scripts to make sure the service starts and stops
    as intended.
    """

    version = 2
    RULES_FILE = '/run/usbguard/rules.conf'

    def __init__(self, *args, **kwargs):
        """Constructs a  security_Usbguard test.
        """
        super(security_Usbguard, self).__init__(*args, **kwargs)
        self._chrome = None

    def __del__(self):
        """Destructs a  security_Usbguard test.
        """
        self.close_chrome()
        super(security_Usbguard, self).__del__()

    def close_chrome(self):
        """This closes the Chrome window if it is still open.
        """
        if self._chrome:
            self._chrome.close()
            self._chrome = None

    def set_usbguard_feature_enabled(self, enabled):
        """Opens Chrome with the USBGuard feature enabled if |enabled| evaluates
        True. Otherwise disables the feature.
        """
        self.close_chrome()
        self._chrome = chrome.Chrome(
            extra_browser_args='--%s-features=USBGuard' %
                               ('enable' if enabled else 'disable'))

    def is_usbguard_feature_enabled(self):
        """Returns True if the USBGuard feature is enabled, otherwise False.
        """
        result = utils.system_output(
            'minijail0 -u chronos /usr/bin/dbus-send --system '
            '--type=method_call --print-reply '
            '--dest=org.chromium.ChromeFeaturesService '
            '/org/chromium/ChromeFeaturesService '
            'org.chromium.ChromeFeaturesServiceInterface.IsUsbguardEnabled'
        ).rstrip()
        if result.endswith('boolean false'):
            return False
        if result.endswith('boolean true'):
            return True
        logging.error('USBGuard feature flag D-bus check yielded: \"%s\"',
                      result)
        raise RuntimeError('Unable to get state of USBGuard feature flag!')

    def test_usbguard(self):
        """Performs the basic test in a generic way with respect to whether the
        USBGuard feature is enabled or not.
        """
        usbguard_enabled = self.is_usbguard_feature_enabled()

        upstart.emit_event('screen-locked')
        # Give usbguard-daemon time to run out of restart attempts.
        time.sleep(5)

        upstart.ensure_running('usbguard-wrapper')
        if usbguard_enabled:
            upstart.ensure_running('usbguard')

            # Make sure usbguard-daemon respawns.
            utils.run('killall usbguard-daemon')
            time.sleep(1)
            upstart.ensure_running('usbguard')
        elif upstart.is_running('usbguard'):
            raise RuntimeError('usbguard-daemon running with feature disabled!')
        if not os.path.isfile(self.RULES_FILE):
            raise RuntimeError('"%s" was not generated!' % (self.RULES_FILE,))
        if os.path.getsize(self.RULES_FILE) == 0:
            raise RuntimeError('%s was empty!' % (self.RULES_FILE,))

        upstart.emit_event('screen-unlocked')

        if upstart.is_running('usbguard'):
            raise RuntimeError('usbguard-daemon still running!')
        if upstart.is_running('usbguard-wrapper'):
            raise RuntimeError('usbguard-wrapper cleanup did not execute!')

    def run_once(self):
        """Runs the security_Usbguard test.
        """

        self.set_usbguard_feature_enabled(enabled=True)
        self.test_usbguard()

        self.set_usbguard_feature_enabled(enabled=False)
        self.test_usbguard()
