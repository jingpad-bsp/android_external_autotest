# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime, logging, random, time

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, utils
from autotest_lib.client.common_lib.cros import chrome, cfm_util

LONG_TIMEOUT = 10
SHORT_TIMEOUT = 2
EXT_ID = 'ikfcpmgefdpheiiomgmhlmmkihchmdlj'


class enterprise_CFM_VolumeChangeClient(test.test):
    """Volume changes made in the CFM / hotrod app should be accurately
    reflected in CrOS.
    """
    version = 1


    def _start_hangout_session(self, webview_context):
        """Start a hangout session.

        @param webview_context: Context for hangouts webview.
        @raises error.TestFail if any of the checks fail.
        """
        current_time = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        hangout_name = 'auto-hangout-' + current_time
        logging.info('Session name: %s', hangout_name)

        if not cfm_util.is_ready_to_start_hangout_session(webview_context):
            raise error.TestFail('CFM should be ready to start new session.')

        cfm_util.start_new_hangout_session(webview_context, hangout_name)

        if not cfm_util.is_in_hangout_session(webview_context):
            raise error.TestFail('CFM was not able to start hangout session.')

        if cfm_util.is_ready_to_start_hangout_session(webview_context):
            raise error.TestFail('Is already in hangout session and should not '
                                 'be able to start another session.')

        time.sleep(SHORT_TIMEOUT)

        if cfm_util.is_mic_muted(webview_context):
            cfm_util.unmute_mic(webview_context)


    def _end_hangout_session(self, webview_context):
        """End hangout session.

        @param webview_context: Context for hangouts window.
        """
        cfm_util.end_hangout_session(webview_context)

        if cfm_util.is_in_hangout_session(webview_context):
            raise error.TestFail('CFM should not be in hangout session.')


    def run_once(self, repeat, cmd):
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
            self._start_hangout_session(cfm_webview_context)

            # This is used to trigger crbug.com/614885
            for volume in range(55, 85):
                cfm_util.set_speaker_volume(cfm_webview_context, str(volume))
                time.sleep(random.uniform(0.01, 0.05))

            while repeat:
                cfm_volume = str(random.randrange(0, 100, 1))
                cfm_util.set_speaker_volume(cfm_webview_context, cfm_volume)
                time.sleep(SHORT_TIMEOUT)

                cras_volume = utils.system_output(cmd)
                if cras_volume != cfm_volume:
                    raise error.TestFail('Cras volume (%s) does not match '
                                         'volume set by CFM (%s).' %
                                         (cras_volume, cfm_volume))
                logging.info('Cras volume (%s) matches volume set by CFM (%s)',
                             cras_volume, cfm_volume)

                repeat -= 1

            self._end_hangout_session(cfm_webview_context)
