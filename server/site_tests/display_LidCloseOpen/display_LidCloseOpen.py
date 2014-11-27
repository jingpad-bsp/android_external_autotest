# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a display lid close and open test using the Chameleon board."""

import logging, time

from autotest_lib.client.common_lib import error

from autotest_lib.server.cros.chameleon import chameleon_test

class display_LidCloseOpen(chameleon_test.ChameleonTest):
    """External Display Lid Close/Open test. """
    version = 1

    # Time to check if device is suspended
    TIMEOUT_SUSPEND_CHECK = 2
    # Allowed timeout for the transition of suspend.
    TIMEOUT_SUSPEND_TRANSITION = 10
    # Allowed timeout for the transition of resume.
    TIMEOUT_RESUME_TRANSITION = 20
    # Time to allow lid transition to take effect
    WAIT_TIME_LID_TRANSITION = 5
    # Time to allow display port plug transition to take effect
    WAIT_TIME_PLUG_TRANSITION = 5
    # Plugged status (before_close, after_close, before_open)
    PLUG_CONFIGS = [(True, True, True),
                    (True, False, False),
                    (True, False, True),
                    (False, True, True),
                    (False, True, False)]

    def wait_to_suspend(self):
        """Wait for DUT to suspend.

        @raise TestFail: If fail to suspend in time.
        """
        if not self.host.ping_wait_down(
            timeout=self.TIMEOUT_SUSPEND_TRANSITION):
            raise error.TestFail('Failed to SUSPEND within tieout')
        logging.debug('DUT is suspended.')


    def wait_to_resume(self):
        """Wait for DUT to resume.

        @raise TestFail: if fail to resume in time.
        """
        if not self.host.wait_up(timeout=self.TIMEOUT_RESUME_TRANSITION):
            raise error.TestFail(
                'Failed to RESUME within timeout')
        logging.debug('DUT is resumed.')


    def close_lid(self):
        """Close lid through servo"""
        logging.debug('Closing lid')
        self.host.servo.lid_close()
        time.sleep(self.WAIT_TIME_LID_TRANSITION)


    def open_lid(self):
        """Open the lid through servo"""
        logging.debug('Opening lid')
        self.host.servo.lid_open()
        time.sleep(self.WAIT_TIME_LID_TRANSITION)


    def check_primary_display_on_internal_screen(self):
        """Checks primary display is on onboard/internal screen"""
        if not self.display_facade.is_display_primary(internal=True):
            self.errors.append('Primary display is not on internal screen')


    def check_primary_display_on_external_screen(self):
        """Checks primary display is on external screen"""
        if not self.display_facade.is_display_primary(internal=False):
            self.errors.append('Primary display is not on external screen')


    def check_mode(self):
        """Checks the display mode is as expected"""
        if self.is_mirrored_enabled() is not self.test_mirrored:
            self.errors.append('Display mode %s is not preserved!' %
                                'mirrored' if self.test_mirrored
                                    else 'extended')


    def check_docked(self):
        """Checks DUT is docked"""
        # Device does not suspend
        if self.host.ping_wait_down(timeout=self.TIMEOUT_SUSPEND_TRANSITION):
            raise error.TestFail('Device suspends when docked!')
        # Verify Chameleon displays main screen
        self.check_primary_display_on_external_screen()
        logging.debug('DUT is docked!')
        return self.chameleon_port.wait_video_input_stable(
            timeout=self.WAIT_TIME_LID_TRANSITION)


    def check_still_suspended(self):
        """Checks DUT is (still) suspended"""
        if not self.host.ping_wait_down(timeout=self.TIMEOUT_SUSPEND_CHECK):
            raise error.TestFail('Device does not stay suspended!')
        logging.debug('DUT still suspended')


    def check_external_display(self):
        """Display status check"""
        resolution = self.chameleon_port.get_resolution()
        # Check mode is same as beginning of the test
        self.check_mode()
        # Check connector
        if self.screen_test.check_external_display_connected(
                self.connector_used, self.errors) is None:
            # Check test image
            self.screen_test.test_screen_with_image(
                    resolution, self.test_mirrored, self.errors)


    def run_once(self, host, test_mirrored=False):
        self.host = host
        self.test_mirrored = test_mirrored
        self.errors = list()

        # Check the servo object
        if self.host.servo is None:
            raise error.TestError('Invalid servo object found on the host.')

        # Get connector type used (HDMI,DP,...)
        self.connector_used = self.display_facade.get_external_connector_name()
        # Set main display mode for the test
        self.display_facade.set_mirrored(self.test_mirrored)

        for (plugged_before_close,
             plugged_after_close,
             plugged_before_open) in self.PLUG_CONFIGS:
            is_suspended = False

            # Plug before close
            self.set_plug(plugged_before_close)
            time.sleep(self.WAIT_TIME_PLUG_TRANSITION)

            # Close lid and check
            self.close_lid()
            if plugged_before_close:
                self.check_docked()
            else:
                self.wait_to_suspend()
                is_suspended = True

            # Plug after close and check
            if plugged_after_close is not plugged_before_close:
                self.set_plug(plugged_after_close)
                time.sleep(self.WAIT_TIME_PLUG_TRANSITION)
                if not plugged_before_close:
                    self.check_still_suspended()
                else:
                    self.wait_to_suspend()
                    is_suspended = True

            # Plug before open and check
            if plugged_before_open is not plugged_after_close:
                self.set_plug(plugged_before_open)
                time.sleep(self.WAIT_TIME_PLUG_TRANSITION)
                if not plugged_before_close or not plugged_after_close:
                    self.check_still_suspended()
                else:
                    self.wait_to_suspend()
                    is_suspended = True

            # Open lid and check
            self.open_lid()
            if is_suspended:
                self.wait_to_resume()
                is_suspended = False

            # Check internal screen switch to primary display
            self.check_primary_display_on_internal_screen()

            # Check status
            if plugged_before_open:
                self.check_external_display()
            if self.errors:
                raise error.TestFail('; '.join(set(self.errors)))
