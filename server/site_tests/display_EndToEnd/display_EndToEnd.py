# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a display end-to-end test using the Chameleon board."""

import logging, os, shutil, time

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.chameleon import chameleon_port_finder
from autotest_lib.client.cros.chameleon import chameleon_screen_test
from autotest_lib.client.cros.chameleon import edid
from autotest_lib.server import test
from autotest_lib.server.cros.multimedia import remote_facade_factory


class display_EndToEnd(test.test):
    """External Display end-toend test.

    This test talks to a Chameleon board and a DUT to set up, run, and verify
    DUT behavior response to reboot, login, docked mode, suspend and resume,
    switching mode, etc.
    """
    version = 1

    # Duration of suspend, in second.
    SUSPEND_DURATION = 30
    # Allowed timeout for the transition of suspend.
    SUSPEND_TIMEOUT = 30
    # Allowed timeout for the transition of resume.
    RESUME_TIMEOUT = 30
    # Allowed timeout for reboot.
    REBOOT_TIMEOUT = 60
    # Default waiting time in sec
    WAIT_TIME = 5
    # Crash paths to check for crash meta data
    CRASH_PATHS = ['/var/spool/crash',
                   '/chronos/home/crash'
                   '/home/chronos/user/crash'
                  ]
    # EDID data files names for different ports
    EDID_FILE_NAMES = [('DELL_U3011T_HDMI.txt', 'ASUS_VE258_HDMI.txt'),
                       ('DELL_U3011T_DP.txt', 'ASUS_VE258_DP.txt')]
    NO_LID_BOARDS = ['stumpy', 'panther', 'zako', 'tricky', 'mccloud']

    def remove_crash_data(self):
        """delete crash meta files"""
        for crash_path in self.CRASH_PATHS:
            if os.path.isdir(crash_path):
                shutil.rmtree(crash_path)


    def is_crash_data_present(self):
        """Check for crash meta files"""
        for crash_path in self.CRASH_PATHS:
            if os.path.isdir(crash_path):
                logging.debug('CRASH detected!')
                return True
        return False


    def switch_display_mode(self):
        """Switch from extended to mirror and the opposite"""
        from_mode = 'MIRRORED' if self.test_mirrored else 'EXTENDED'
        self.test_mirrored = not self.test_mirrored
        to_mode = 'MIRRORED' if self.test_mirrored else 'EXTENDED'
        logging.debug('Set mirrored: %s', self.test_mirrored)
        self.display_facade.set_mirrored(self.test_mirrored)
        logging.debug('Switched from %s to %s mode', from_mode, to_mode)
        time.sleep(self.WAIT_TIME)
        self.check_external_resolution()


    def reboot_device(self, plugged_before, plugged_after):
        """Reboot DUT

        @param plugged_before: a boolean, plugged status before reboot
        @param plugged_after: a boolean, plugged status after reboot

        """

        boot_id = self.host.get_boot_id()
        self.chameleon_port.set_plug(plugged_before)
        logging.debug('Reboot...')
        self.host.reboot(wait=False)
        time.sleep(self.WAIT_TIME)
        self.host.test_wait_for_shutdown(self.REBOOT_TIMEOUT)
        self.host.test_wait_for_boot(boot_id)
        self.chameleon_port.set_plug(plugged_after)


    def test_suspend_resume(self, plugged_before_suspend,
                            plugged_after_suspend, plugged_after_resume):
        """Suspends and resumes the DUT with different connections status
        before suspend, after suspend, and after resume

        @param plugged_before_suspend: a boolean, plugged before suspend
        @param plugged_after_suspend: a boolean, plugged after suspend
        @param plugged_after_resume: a boolean, plugged after resume

        """
        boot_id = self.host.get_boot_id()
        # Plug before suspend
        self.chameleon_port.set_plug(plugged_before_suspend)
        time.sleep(self.WAIT_TIME)
        logging.debug('Going to suspend, for %d seconds...',
                     self.SUSPEND_DURATION)
        time_before_suspend = time.time()
        self.display_facade.suspend_resume_bg(self.SUSPEND_DURATION)

        # Confirm DUT suspended.
        self.host.test_wait_for_sleep(self.SUSPEND_TIMEOUT)
        if plugged_before_suspend is not plugged_after_suspend:
            self.chameleon_port.set_plug(plugged_after_suspend)

        current_time = time.time()
        sleep_time = (self.SUSPEND_DURATION -
                      (current_time - time_before_suspend))
        logging.debug('Wait for %.2f seconds...', sleep_time)
        time.sleep(sleep_time)

        self.host.test_wait_for_resume(boot_id, self.RESUME_TIMEOUT)
        logging.debug('Resumed ')

        if plugged_after_resume is not plugged_after_suspend:
            self.chameleon_port.set_plug(plugged_after_resume)


    def check_external_display(self):
        """Display status check"""
        # Check connector and test image
        if self.screen_test.check_external_display_connected(
                self.connector_used, self.errors) is None:
            self.screen_test.test_screen_with_image(
                    self.resolution, self.test_mirrored, self.errors)
        # Check for crashes.
        if self.is_crash_data_present():
            self.errors.append('Crash data is detected on DUT')
        # Check for errors
        if self.errors:
            raise error.TestFail('; '.join(set(self.errors)))


    def get_edids_filepaths(self):
        """Gets the EDID data files for the connector type used"""
        if self.connector_used.startswith('HDMI'):
            first_edid,second_edid = self.EDID_FILE_NAMES[0]
        elif self.connector_used.startswith('DP'):
            first_edid,second_edid = self.EDID_FILE_NAMES[1]
        first_edid = os.path.join(self.bindir, 'test_data/edids', first_edid)
        second_edid = os.path.join(self.bindir, 'test_data/edids', second_edid)
        return (first_edid, second_edid)


    def check_external_resolution(self):
        """Checks the external screen resolution."""
        # Wait video stable, making sure CrOS switches to a proper resolution.
        self.chameleon_port.wait_video_input_stable()
        # Get the resolution for the edid applied
        self.resolution = utils.wait_for_value_changed(
                self.display_facade.get_external_resolution,
                old_value=(0, 0))
        logging.debug('External display resolution: %s',
                str(self.resolution))


    def apply_edid(self, edid_file):
        """Apply EDID from a file

        @param edid_file: file path to edid data

        """
        self.display_facade.apply_edid(edid.Edid.from_file(edid_file))


    def dock_dut(self):
        """Close lid(assumes device is connected to chameleon)"""
        board = self.host.get_board().split(':')[1]
        logging.debug('Docking the DUT!')
        if board not in self.NO_LID_BOARDS:
            self.host.servo.lid_close()
            time.sleep(self.WAIT_TIME)
            return True
        else:
            logging.debug('DUT does not dock!')
            return False


    def undock_dut(self):
        """Open the lid"""
        self.host.servo.lid_open()
        time.sleep(self.WAIT_TIME)


    def run_once(self, host, test_mirrored=False):
        self.host = host
        self.test_mirrored = test_mirrored
        self.errors = []

        # Check the servo object
        if self.host.servo is None:
            raise error.TestError('Invalid servo object found on the host.')

        # Remove any crash data before test procedure
        if self.is_crash_data_present():
            self.remove_crash_data()

        factory = remote_facade_factory.RemoteFacadeFactory(host)
        display_facade = factory.create_display_facade()
        chameleon_board = host.chameleon

        chameleon_board.reset()
        finder = chameleon_port_finder.ChameleonVideoInputFinder(
                chameleon_board, display_facade)
        for chameleon_port in finder.iterate_all_ports():
            self.run_test_on_port(chameleon_port, display_facade)


    def run_test_on_port(self, chameleon_port, display_facade):
        """Run the test on the given Chameleon port.

        @param chameleon_port: a ChameleonPorts object.
        @param display_facade: a display facade object.
        """
        self.chameleon_port = chameleon_port
        self.display_facade = display_facade
        self.screen_test = chameleon_screen_test.ChameleonScreenTest(
                chameleon_port, display_facade, self.outputdir)

        self.connector_used = self.display_facade.get_external_connector_name()
        first_edid, second_edid = self.get_edids_filepaths()

        # Set first monitor/EDID and tracked resolution
        with self.chameleon_port.use_edid_file(first_edid):
            self.check_external_resolution()
            # Set main display mode for the test
            logging.debug('Set mirrored: %s', self.test_mirrored)
            self.display_facade.set_mirrored(self.test_mirrored)

            logging.debug('- Stage  1 - reboot')
            # Reboot the device as connected and login
            self.reboot_device(plugged_before=True, plugged_after=True)
            # Check status
            self.check_external_display()

            logging.debug('- Stage  2 - dock-undock-switch mode and back')
            # Dock and undock (close lid and open lid)
            if self.dock_dut():
                self.undock_dut();

            # Switch mode
            self.switch_display_mode()
            # Switch mode back
            self.switch_display_mode()
            self.check_external_display()

            # Suspend and resume as currently plugged
            logging.debug('- Stage  3 - suspend-resume')
            self.test_suspend_resume(plugged_before_suspend=True,
                                     plugged_after_suspend=True,
                                     plugged_after_resume=True)

            # Check status
            self.check_external_display()

            logging.debug('- Stage  4 - unplug-suspend-plug-resume')
            # Unplug-Suspend-Plug-Resume
            self.test_suspend_resume(plugged_before_suspend=False,
                                     plugged_after_suspend=True,
                                     plugged_after_resume=True)
            # Check status
            self.check_external_display()

            logging.debug('- Stage  5 - suspend-unplug-resume-plug')
            # Suspens-Unplug-Resume-Plug
            self.test_suspend_resume(plugged_before_suspend=True,
                                     plugged_after_suspend=False,
                                     plugged_after_resume=True)
            # Check status
            self.check_external_display()

            logging.debug('- Stage  6 - dock-unplug1/suspend-plug2-undock')
            # Docked mode(close lid)
            if self.dock_dut():
                logging.debug('Unplug display')
                # Unplug, thus DUT should suspend
                self.chameleon_port.set_plug(False)
                self.host.test_wait_for_sleep(self.SUSPEND_TIMEOUT)
                logging.debug('DUT is suspended')

        # Plug the second monitor while suspended
        with self.chameleon_port.use_edid_file(second_edid):
            self.chameleon_port.set_plug(True)

            # Resume(open lid), doesn't hurt if DUT is not docked
            self.undock_dut()
            self.host.wait_up(self.RESUME_TIMEOUT)

            # Set mode back to mirror after resuming with diff monitor
            if self.test_mirrored:
                self.switch_display_mode()

            # Check status
            self.check_external_display()

            logging.debug('- Stage  7 - unplug2-plug1')
            # Unplug and plug the original monitor
            self.chameleon_port.set_plug(False)

        with self.chameleon_port.use_edid_file(first_edid):
            self.chameleon_port.set_plug(True)

            # Update the resolution
            self.check_external_resolution()

            # Check status
            self.check_external_display()
