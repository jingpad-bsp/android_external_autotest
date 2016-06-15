# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, time

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome, cfm_util

SHORT_TIMEOUT = 2
EXT_ID = 'ikfcpmgefdpheiiomgmhlmmkihchmdlj'


class enterprise_CFM_USBPeripheralDetect(test.test):
    """Tests that the peripherals detected by the hotrod app match those
    detected by CrOS in the server side test.
    """
    version = 1


    def set_preferred_peripherals(self, webview_context, cros_peripherals):
        """Set perferred peripherals.

        @param webview_context: Context for hangouts window.
        """
        cfm_util.wait_for_telemetry_commands(webview_context)
        cfm_util.wait_for_oobe_start_page(webview_context)

        if not cfm_util.is_oobe_start_page(webview_context):
            raise error.TestFail('CFM did not reach oobe screen.')

        cfm_util.skip_oobe_screen(webview_context)
        time.sleep(SHORT_TIMEOUT)

        avail_mics = cfm_util.get_mic_devices(webview_context)
        avail_speakers = cfm_util.get_speaker_devices(webview_context)
        avail_cameras = cfm_util.get_camera_devices(webview_context)

        if cros_peripherals.get('Microphone') in avail_mics:
            cfm_util.set_preferred_mic(
                    webview_context, cros_peripherals.get('Microphone'))
        if cros_peripherals.get('Speaker') in avail_speakers:
            cfm_util.set_preferred_speaker(
                    webview_context, cros_peripherals.get('Speaker'))
        if cros_peripherals.get('Camera') in avail_cameras:
            cfm_util.set_preferred_camera(
                    webview_context, cros_peripherals.get('Camera'))


    def peripheral_detection(self, webview_context):
        """Get attached peripheral information.

        @param webview_context: Context for hangouts window.
        """
        cfm_peripheral_dict = {'Microphone': None, 'Speaker': None,
                               'Camera': None}

        cfm_peripheral_dict['Microphone'] = cfm_util.get_preferred_mic(
                webview_context)
        cfm_peripheral_dict['Speaker'] = cfm_util.get_preferred_speaker(
                webview_context)
        cfm_peripheral_dict['Camera'] = cfm_util.get_preferred_camera(
                webview_context)

        for device_type, is_found in cfm_peripheral_dict.iteritems():
            if not is_found:
                cfm_peripheral_dict[device_type] = 'Not Found'

        return cfm_peripheral_dict


    def run_once(self, cros_peripheral_dict):
        """Runs the test."""
        with chrome.Chrome(clear_enterprise_policy=False,
                           dont_override_profile=True,
                           disable_gaia_services=False,
                           disable_default_apps=False,
                           auto_login=False) as cr:
            cfm_webview_context = cfm_util.get_cfm_webview_context(
                    cr.browser, EXT_ID)
            self.set_preferred_peripherals(cfm_webview_context,
                                           cros_peripheral_dict)
            cfm_peripheral_dict = self.peripheral_detection(cfm_webview_context)
            logging.debug('Peripherals detected by hotrod: %s',
                          cfm_peripheral_dict)

            cros_peripherals = set(cros_peripheral_dict.iteritems())
            cfm_peripherals = set(cfm_peripheral_dict.iteritems())

            peripheral_diff = cros_peripherals.difference(cfm_peripherals)

            if peripheral_diff:
                no_match_list = list()
                for item in peripheral_diff:
                    no_match_list.append(item[0])

                raise error.TestFail('Following peripherals do not match: %s' %
                                     ', '.join(no_match_list))
