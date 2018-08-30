# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import time

from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros.input_playback import keyboard
from autotest_lib.client.cros.power import power_test

class power_ThermalLoad(power_test.power_Test):
    """class for power_WebGL test.
    """
    version = 1

    URL = 'https://arodic.github.io/p/jellyfish/'
    HOUR = 60 * 60

    def run_once(self, url=URL, duration=2.5 * HOUR):
        """run_once method.

        @param url: url of webgl heavy page.
        @param duration: time in seconds to display url and measure power.
        """
        with chrome.Chrome(init_network_controller=True) as self.cr:
            tab = self.cr.browser.tabs.New()
            tab.Activate()

            # Just measure power in full-screen.
            fullscreen = tab.EvaluateJavaScript('document.webkitIsFullScreen')
            if not fullscreen:
                with keyboard.Keyboard() as keys:
                    keys.press_key('f4')

            self.backlight.set_percent(100)

            logging.info('Navigating to url: %s', url)
            tab.Navigate(url)
            tab.WaitForDocumentReadyStateToBeComplete()

            # Change param to 100 fast moving jellyfish.
            tab.EvaluateJavaScript('$("#jCount").val(100);')
            tab.EvaluateJavaScript('$("#jSpeed").val(0.1);')

            # Jellyfish is added one by one. Wait until we actually have 100.
            while tab.EvaluateJavaScript('jellyfish.count') < 100:
                time.sleep(0.1)

            self.start_measurements()
            time.sleep(duration)
