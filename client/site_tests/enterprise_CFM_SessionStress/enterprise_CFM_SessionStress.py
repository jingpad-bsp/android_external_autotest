# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime, logging, time

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome, cfm_util

LONG_TIMEOUT = 7
SHORT_TIMEOUT = 2
EXT_ID = 'ikfcpmgefdpheiiomgmhlmmkihchmdlj'


class enterprise_CFM_SessionStress(test.test):
    """Stress tests the device in CFM kiosk mode by initiating a new hangout
    session multiple times.
    """
    version = 1


    def _run_hangout_session(self, webview_context):
        """Start a hangout session and do some checks before ending the session.

        @param webview_context: Context for hangouts webview.
        @raises error.TestFail if any of the checks fail.
        """
        current_time = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        hangout_name = 'auto-hangout-' + current_time
        logging.info('Session name: %s', hangout_name)

        cfm_util.start_new_hangout_session(webview_context, hangout_name)
        time.sleep(LONG_TIMEOUT)
        cfm_util.end_hangout_session(webview_context)


    def run_once(self, repeat):
        """Runs the test."""
        with chrome.Chrome(clear_enterprise_policy=False,
                           dont_override_profile=True,
                           disable_gaia_services=False,
                           disable_default_apps=False,
                           auto_login=False) as cr:
            cfm_webview_context = cfm_util.get_cfm_webview_context(
                    cr.browser, EXT_ID)

            cfm_util.wait_for_telemetry_commands(cfm_webview_context)
            cfm_util.wait_for_oobe_start_page(cfm_webview_context)

            if not cfm_util.is_oobe_start_page(cfm_webview_context):
                raise error.TestFail('CFM did not reach oobe screen.')

            cfm_util.skip_oobe_screen(cfm_webview_context)

            while repeat:
                self._run_hangout_session(cfm_webview_context)
                time.sleep(SHORT_TIMEOUT)
                repeat -= 1

