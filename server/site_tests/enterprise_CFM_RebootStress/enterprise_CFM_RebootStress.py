# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import tpm_utils
from autotest_lib.server import test
from autotest_lib.server.cros.multimedia import remote_facade_factory


SHORT_TIMEOUT = 5

class enterprise_CFM_RebootStress(test.test):
    """Stress tests the CFM enrolled device by rebooting it multiple times using
    Chrome runtime restart() API and ensuring the packaged app launches as
    expected after every reboot.
    """
    version = 1


    def run_once(self, host, repeat, is_meeting=False):
        """Runs the test."""
        self.client = host

        factory = remote_facade_factory.RemoteFacadeFactory(
                host, no_chrome=True)
        self.cfm_facade = factory.create_cfm_facade()

        tpm_utils.ClearTPMOwnerRequest(self.client)

        if self.client.servo:
            self.client.servo.switch_usbkey('dut')
            self.client.servo.set('usb_mux_sel3', 'dut_sees_usbkey')
            time.sleep(SHORT_TIMEOUT)
            self.client.servo.set('dut_hub1_rst1', 'off')
            time.sleep(SHORT_TIMEOUT)

        try:
            self.cfm_facade.enroll_device()

            # Reboot and sleep are a hack for devtools crash issue tracked in
            # crbug.com/739474.
            self.client.reboot()
            time.sleep(SHORT_TIMEOUT)
            self.cfm_facade.skip_oobe_after_enrollment()

            while repeat:
                boot_id = self.client.get_boot_id()
                if is_meeting:
                    self.cfm_facade.wait_for_meetings_landing_page()
                else:
                    self.cfm_facade.wait_for_hangouts_telemetry_commands()
                self.cfm_facade.reboot_device_with_chrome_api()
                self.client.wait_for_restart(old_boot_id=boot_id)
                self.cfm_facade.restart_chrome_for_cfm()
                repeat -= 1

        except Exception as e:
            raise error.TestFail(str(e))
        finally:
            tpm_utils.ClearTPMOwnerRequest(self.client)
