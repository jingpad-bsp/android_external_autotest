# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.server import test
from autotest_lib.client.common_lib import error

class platform_StageAndRecover(test.test):
    """Installs the same version recovery image onto a servo-connected DUT."""
    version = 1

    _RECOVERY_INSTALL_DELAY = 540

    def cleanup(self):
        """ Clean up by switching servo usb towards servo host. """
        self.switch_usbkey('host')


    def set_servo_usb_reimage(self):
        """ Turns USB_HUB_2 servo port to DUT, and disconnects servo from DUT.
        Avoiding peripherals plugged at this servo port.
        """
        self.host.servo.set('usb_mux_sel3', 'dut_sees_usbkey')
        self.host.servo.set('dut_hub1_rst1','on')

    def set_servo_usb_recover(self):
        """ Turns USB_HUB_2 servo port to servo, and connects servo to DUT.
        Avoiding peripherals plugged at this servo port.
        """
        self.host.servo.set('usb_mux_sel3', 'servo_sees_usbkey')
        self.host.servo.set('dut_hub1_rst1','off')

    def run_once(self, host):
        self.host = host

        # Stage the recovery image on dev server
        image_path = self.host.stage_image_for_servo(
            self.host.get_release_builder_path(),
            artifact='recovery_image')
        logging.info('Image staged at %s', image_path)

        # Make sermo sees only DUT_HUB1
        self.set_servo_usb_reimage()
        # Reimage servo USB
        self.host.servo.image_to_servo_usb(image_path,
                                           make_image_noninteractive=True)
        self.set_servo_usb_recover()

        # Boot DUT in recovery mode for image to install
        self.host.servo.boot_in_recovery_mode()

        logging.info('Running the recovery process on the DUT. '
                     'Will wait up to %d seconds for recovery to '
                     'complete.', self._RECOVERY_INSTALL_DELAY)
        start_time = time.time()
        # Wait for the host to come up.
        if host.ping_wait_up(timeout=self._RECOVERY_INSTALL_DELAY):
            logging.info('Recovery process completed successfully in '
                         '%d seconds.', time.time() - start_time)
        else:
            raise error.TestFail('Host failed to come back up after '
                                 '%d seconds.' % self._RECOVERY_INSTALL_DELAY)
