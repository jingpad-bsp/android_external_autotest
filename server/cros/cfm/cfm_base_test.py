# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import time

from autotest_lib.server import test
from autotest_lib.client.common_lib.cros import tpm_utils
from autotest_lib.server.cros.multimedia import remote_facade_factory

SHORT_TIMEOUT = 5


class CfmBaseTest(test.test):
    """
    Base class for Cfm enterprise tests.

    CfmBaseTest provides common setup and cleanup methods. This base class is
    agnostic with respect to 'hangouts classic' vs. 'hangouts meet' - it works
    for both flavors.
    """

    def initialize(self, host):
        """
        Initializes common test properties.

        @param host: a host object representing the DUT.
        """
        super(CfmBaseTest, self).initialize()
        self._host = host
        factory = remote_facade_factory.RemoteFacadeFactory(self._host,
                                                            no_chrome = True)
        self.cfm_facade = factory.create_cfm_facade()

    def setup(self):
        """
        Performs common test setup operations:
          - clears the TPM
          - sets up servo
          - enrolls the device
          - skips OOBE
        """
        super(CfmBaseTest, self).setup()
        tpm_utils.ClearTPMOwnerRequest(self._host)
        if self._host.servo:
            self._setup_servo()
        self.cfm_facade.enroll_device()
        self.cfm_facade.skip_oobe_after_enrollment()

    def _setup_servo(self):
        """
        Enables the USB port such that any peripheral connected to it is visible
        to the DUT.
        """
        self._host.servo.switch_usbkey('dut')
        self._host.servo.set('usb_mux_sel3', 'dut_sees_usbkey')
        time.sleep(SHORT_TIMEOUT)
        self._host.servo.set('dut_hub1_rst1', 'off')
        time.sleep(SHORT_TIMEOUT)

    def cleanup(self):
        """Takes a screenshot and clears the TPM."""
        self.take_screenshot('%s' % self.tagged_testname)
        tpm_utils.ClearTPMOwnerRequest(self._host)
        super(CfmBaseTest, self).cleanup()

    def take_screenshot(self, screenshot_name):
        """
        Takes a screenshot (in .png format) and saves it in the debug dir.

        @param screenshot_name: Name of the screenshot file without extension.
        """
        try:
            target_dir = self.debugdir
            logging.info('Taking screenshot and saving under %s...',
                         target_dir)
            remote_path = self.cfm_facade.take_screenshot()
            if remote_path:
                # Copy the screenshot from the DUT.
                self._host.get_file(
                    remote_path,
                    os.path.join(target_dir, screenshot_name + '.png'))
            else:
                logging.warning('Taking screenshot failed')
        except Exception as e:
            logging.warning('Exception while taking a screenshot', exc_info = e)

