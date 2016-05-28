# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime, logging, time

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome, cfm_util

LONG_TIMEOUT = 10
SHORT_TIMEOUT = 2
EXT_ID = 'ikfcpmgefdpheiiomgmhlmmkihchmdlj'
FAILED_TEST_LIST = list()


class enterprise_CFM_Sanity(test.test):
    """Tests the following fuctionality works on CFM enrolled devices:
           1. Is able to reach the oobe screen
           2. Is able to start a hangout session
           3. Should not be able to start a hangout session if already in a
              session.
           4. Exits hangout session successfully.
           5. Should be able to start a hangout session if currently not in
              a session.
           6. Is able to detect attached peripherals: mic, speaker, camera.
           7. Is able to run hotrod diagnostics.
    """
    version = 1


    def _hangouts_sanity_test(self, webview_context):
        """Execute a series of test actions and perform verifications.

        @param webview_context: Context for hangouts webview.
        @raises error.TestFail if any of the checks fail.
        """
        current_time = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        hangout_name = 'auto-hangout-' + current_time

        cfm_util.wait_for_telemetry_commands(webview_context)
        cfm_util.wait_for_oobe_start_page(webview_context)

        if not cfm_util.is_oobe_start_page(webview_context):
            raise error.TestFail('CFM did not reach oobe screen.')

        cfm_util.skip_oobe_screen(webview_context)

        if cfm_util.is_ready_to_start_hangout_session(webview_context):
            cfm_util.start_new_hangout_session(webview_context, hangout_name)

        if not cfm_util.is_in_hangout_session(webview_context):
            raise error.TestFail('CFM was not able to start hangout session.')

        time.sleep(LONG_TIMEOUT)
        cfm_util.unmute_mic(webview_context)

        if cfm_util.is_ready_to_start_hangout_session(webview_context):
            raise error.TestFail('Is already in hangout session and should not '
                                 'be able to start another session.')

        if cfm_util.is_oobe_start_page(webview_context):
            raise error.TestFail('CFM should be in hangout session and not on '
                                 'oobe screen.')

        time.sleep(SHORT_TIMEOUT)
        cfm_util.mute_mic(webview_context)
        time.sleep(SHORT_TIMEOUT)
        cfm_util.end_hangout_session(webview_context)

        if cfm_util.is_in_hangout_session(webview_context):
            raise error.TestFail('CFM should not be in hangout session.')

        if cfm_util.is_oobe_start_page(webview_context):
            raise error.TestFail('CFM should not be on oobe screen.')

        if not cfm_util.is_ready_to_start_hangout_session(webview_context):
            raise error.TestFail('CFM should be in read state to start hangout '
                           'session.')


    def _peripherals_sanity_test(self, webview_context):
        """Checks for connected peripherals.

        @param webview_context: Context for hangouts webview.
        """
        cfm_util.wait_for_telemetry_commands(webview_context)

        time.sleep(SHORT_TIMEOUT)

        if not cfm_util.get_mic_devices(webview_context):
            FAILED_TEST_LIST.append('No mic detected')

        if not cfm_util.get_speaker_devices(webview_context):
            FAILED_TEST_LIST.append('No speaker detected')

        if not cfm_util.get_camera_devices(webview_context):
            FAILED_TEST_LIST.append('No camera detected')

        if not cfm_util.get_preferred_mic(webview_context):
            FAILED_TEST_LIST.append('No preferred mic')

        if not cfm_util.get_preferred_speaker(webview_context):
            FAILED_TEST_LIST.append('No preferred speaker')

        if not cfm_util.get_preferred_camera(webview_context):
            FAILED_TEST_LIST.append('No preferred camera')


    def _diagnostics_sanity_test(self, webview_context):
        """Runs hotrod diagnostics and checks status.

        @param webview_context: Context for hangouts webview.
        @raise error.TestFail if diagnostic checks fail.
        """
        cfm_util.wait_for_telemetry_commands(webview_context)

        if cfm_util.is_diagnostic_run_in_progress(webview_context):
            raise error.TestFail('Diagnostics should not be running.')

        cfm_util.run_diagnostics(webview_context)

        if not cfm_util.is_diagnostic_run_in_progress(webview_context):
            raise error.TestFail('Diagnostics should be running.')

        diag_results = cfm_util.get_last_diagnostics_results(webview_context)

        if diag_results['status'] not in 'success':
            logging.debug(diag_results['childrens'])
            FAILED_TEST_LIST.append('Diagnostics failed')


    def run_once(self):
        """Runs the test."""
        with chrome.Chrome(clear_enterprise_policy=False,
                           dont_override_profile=True,
                           disable_gaia_services=False,
                           disable_default_apps=False,
                           auto_login=False) as cr:
            cfm_webview_context = cfm_util.get_cfm_webview_context(
                    cr.browser, EXT_ID)
            self._hangouts_sanity_test(cfm_webview_context)
            self._peripherals_sanity_test(cfm_webview_context)
            self._diagnostics_sanity_test(cfm_webview_context)

        if FAILED_TEST_LIST:
            raise error.TestFail('Test failed because of following reasons: %s'
                                 % ', '.join(map(str, FAILED_TEST_LIST)))
