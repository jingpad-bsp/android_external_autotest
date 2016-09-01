# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


""" The autotest performing FW update, both EC and AP."""


import logging

from autotest_lib.client.common_lib import error
from autotest_lib.server import afe_utils
from autotest_lib.server import test


class provision_FirmwareUpdate(test.test):
    """A test that can provision a machine to the correct firmware version."""

    version = 1


    def stage_image_to_usb(self, host):
        """Stage the current ChromeOS image on the USB stick connected to the
        servo.

        @param host:  a CrosHost object of the machine to update.
        """
        cros_image_labels = afe_utils.get_labels(host, host.VERSION_PREFIX)
        if not cros_image_labels:
            logging.warn('Failed to get version label from the DUT, skip '
                         'staging ChromeOS image on the servo USB stick.')
        else:
            cros_image_name = cros_image_labels[0][len(
                    host.VERSION_PREFIX + ':'):]
            host.servo.image_to_servo_usb(
                    host.stage_image_for_servo(cros_image_name))
            logging.debug('ChromeOS image %s is staged on the USB stick.',
                          cros_image_name)


    def run_once(self, host, value, rw_only=False, stage_image_to_usb=False):
        """The method called by the control file to start the test.

        @param host:  a CrosHost object of the machine to update.
        @param value: the provisioning value, which is the build version
                      to which we want to provision the machine,
                      e.g. 'link-firmware/R22-2695.1.144'.
        @param rw_only: True to only update the RW firmware.
        @param stage_image_to_usb: True to stage the current ChromeOS image on
                the USB stick connected to the servo. Default is False.
        """
        try:
            host.repair_servo()

            # Stage the current CrOS image to servo USB stick.
            if stage_image_to_usb:
                self.stage_image_to_usb(host)

            host.firmware_install(build=value, rw_only=rw_only)
        except Exception as e:
            logging.error(e)
            raise error.TestFail(str(e))
