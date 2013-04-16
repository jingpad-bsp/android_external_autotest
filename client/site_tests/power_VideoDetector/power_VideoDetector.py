# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import base_utils, error
from autotest_lib.client.cros import cros_ui_test, power_utils

class power_VideoDetector(cros_ui_test.UITest):
    version = 1

    def initialize(self):
        super(power_VideoDetector, self).initialize()
        self._video_url = \
            'file://%s/tests/power_VideoDetector/fade.html' % self.autodir


    def run_once(self, run_time_sec=60):
        if run_time_sec < 30:
            raise error.TestError('Must run for at least 30 seconds')

        self.login()

        # Start powerd if not started.  Set timeouts for quick idle events.
        run_time_ms = run_time_sec * 1000
        # At the time of writing this test, the video detector gets a status
        # update from Chrome every ten seconds.
        react_ms = 5000
        dim_ms = 10000
        off_ms = max(3600000, run_time_ms * 10)
        prefs = { 'disable_als'            : 1,
                  'ignore_external_policy' : 1,
                  'plugged_dim_ms'         : dim_ms,
                  'plugged_off_ms'         : off_ms,
                  'unplugged_dim_ms'       : dim_ms,
                  'unplugged_off_ms'       : off_ms, }
        self._pref_change = power_utils.PowerPrefChanger(prefs)

        keyvals = {}

        # Start with max brightness, so we can easily detect dimming.
        power_utils.BacklightController().set_brightness_to_max()
        backlight = power_utils.Backlight()
        initial_brightness = base_utils.wait_for_value(backlight.get_max_level)

        # Open a tab to play video.
        self.pyauto.AppendTab(self._video_url)

        # Sleep until the runtime is up.
        time.sleep(run_time_sec)

        # Stop powerd to avoid dimming when the video stops.
        utils.system_output('stop powerd')

        final_brightness = backlight.get_level()

        # Check that the backlight stayed the same.
        if initial_brightness != final_brightness:
            raise error.TestFail(
                ('Backlight level changed from %d to %d when it should ' + \
                 'have stayed the same.') %
                (initial_brightness, final_brightness))

        keyvals['initial_brightness'] = initial_brightness
        keyvals['final_brightness'] = final_brightness
        self.write_perf_keyval(keyvals)


    def cleanup(self):
        if self.logged_in():
            self.logout()
        utils.restart_job('powerd')
