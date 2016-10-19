# Copyright (c) 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import os
import re
import time

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.faft.firmware_test import FirmwareTest

class firmware_EmmcWriteLoad(FirmwareTest):
    """
    Runs chromeos-install repeatedly while monitoring dmesg output for EMMC
    timeout errors.

    This test requires a USB disk plugged-in, which contains a Chrome OS test
    image (built by "build_image test"). On runtime, this test first switches
    DUT to developer mode. When dev_boot_usb=0, pressing Ctrl-U on developer
    screen should not boot the USB disk. When dev_boot_usb=1, pressing Ctrl-U
    should boot the USB disk.

    The length of time in minutes should be specified by the parameter
    -a 'minutes_to_run=240'
    """
    version = 1

    INSTALL_COMMAND = '/usr/sbin/chromeos-install --yes'
    ERROR_MESSAGE_REGEX = re.compile(
            r'mmc[0-9]+: Timeout waiting for hardware interrupt', re.MULTILINE)

    def initialize(self, host, cmdline_args, ec_wp=None):
      dict_args = utils.args_to_dict(cmdline_args)
      self.minutes_to_run = int(dict_args.get('minutes_to_run', 5))
      super(firmware_EmmcWriteLoad, self).initialize(
              host, cmdline_args, ec_wp=ec_wp)

      self.assert_test_image_in_usb_disk()
      self.switcher.setup_mode('dev')
      self.setup_usbkey(usbkey=True, host=False)

      self.original_dev_boot_usb = self.faft_client.system.get_dev_boot_usb()
      logging.info(
              'Original dev_boot_usb value: %s', str(self.original_dev_boot_usb))


    def read_dmesg(self, filename):
        """Put the contents of 'dmesg -cT' into the given file.

        @param filename: The file to write 'dmesg -cT' into.
        """
        with open(filename, 'w') as f:
            self._client.run('dmesg -cT', stdout_tee=f)

        return utils.read_file(filename)

    def check_for_emmc_error(self, dmesg, error_regex):
      """Check the current dmesg output for the specified error message regex.

      @param dmesg: Contents of the dmesg buffer.
      @param error_regex: The regex to check for the error.

      @return True if error found.
      """
      for line in dmesg.splitlines():
        if error_regex.search(dmesg):
          return True

      return False

    def install_chrome_os(self):
      """Runs the install command in a continuous loop. """
      install = 'while true; do %s; done' % self.INSTALL_COMMAND
      self.install_process = self._client.run_background(install)

    def poll_for_emmc_error(self, dmesg_file, poll_seconds=20):
        end_time = datetime.datetime.now() +
                datetime.timedelta(minutes=self.minutes_to_run)

        while datetime.datetime.now() <= end_time:
          dmesg = self.read_dmesg(dmesg_file)
          contains_error = self.check_for_emmc_error(
              dmesg, self.ERROR_MESSAGE_REGEX)
          if contains_error:
            raise error.TestFail('eMMC error found. Dmesg output: %s' % dmesg)
          time.sleep(poll_seconds)

    def cleanup(self):
        self.ensure_internal_device_boot()
        super(firmware_EmmcWriteLoad, self).cleanup()

    def ensure_internal_device_boot(self):
        """Ensure internal device boot; if not, reboot into it.

        If not, it may be a test failure during step 2 or 3, try to reboot
        and press Ctrl-D to internal device boot.
        """
        if self.faft_client.system.is_removable_device_boot():
            logging.info('Reboot into internal disk...')
            self.faft_client.system.set_dev_boot_usb(self.original_dev_boot_usb)
            self.switcher.mode_aware_reboot()

    def run_once(self):
        self.faft_client.system.set_dev_boot_usb(1)
        self.switcher.mode_aware_reboot(wait_for_dut_up=False)
        self.switcher.bypass_dev_boot_usb()
        self.switcher.wait_for_client()

        logging.info('Expected USB boot, set dev_boot_usb to the original.')
        self.check_state((self.checkers.dev_boot_usb_checker,
                          True,
                          'Not USB boot, Ctrl-U not work'))

        dmesg_filename = os.path.join(self.resultsdir, 'dmesg')

        logging.info('===== Starting OS install loop. =====')
        logging.info(
            '===== Running install for %s minutes. =====' % self.minutes_to_run)
        self.install_chrome_os()

        self.poll_for_emmc_error(dmesg_file=dmesg_filename)

        logging.info('Killing ChromeOS install loop.')
        self._client.run('kill -9 %s' % self.install_process)

        logging.info('Run one last install.')
        self._client.run(self.INSTALL_COMMAND)
