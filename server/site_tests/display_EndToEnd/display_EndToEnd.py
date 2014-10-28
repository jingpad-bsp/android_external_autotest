# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a display end-to-end test using the Chameleon board."""

import logging, os, shutil, time

from autotest_lib.client.common_lib import error

from autotest_lib.server.cros.chameleon import chameleon_test


class display_EndToEnd(chameleon_test.ChameleonTest):
    """External Display end-toend test.

    This test talks to a Chameleon board and a DUT to set up, run, and verify
    DUT behavior response to reboot, login, docked mode, suspend and resume,
    switching mode, etc.
    """
    version = 1

    # Duration of suspend, in second.
    SUSPEND_DURATION = 15
    # Allowed timeout for the transition of suspend.
    SUSPEND_TIMEOUT = 7
    # Allowed timeout for the transition of resume.
    RESUME_TIMEOUT = 20
    #Default waiting time in sec
    WAIT_TIME = 5
    #Crash paths to check for crash meta data
    CRASH_PATHS = ['/var/spool/crash',
                   '/chronos/home/crash'
                   '/home/chronos/user/crash'
                  ]
    #EDID data files names for different ports
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
        self.set_mirrored(self.test_mirrored)
        logging.debug('Switched from %s to %s mode', from_mode, to_mode)
        time.sleep(self.WAIT_TIME)
        self.reconnect_and_get_external_resolution()


    def reboot_device(self, plugged_before, plugged_after):
        """Reboot DUT

        @param plugged_before: a boolean, plugged status before reboot
        @param plugged_after: a boolean, plugged status after reboot

        """

        boot_id = self.host.get_boot_id()
        self.set_plug(plugged_before)
        self.reboot(wait=False)
        self.host.test_wait_for_shutdown()
        self.host.test_wait_for_boot(boot_id)
        self.set_plug(plugged_after)
        self.display_facade.connect()


    def suspend_resume(self, plugged_before_suspend,
                          plugged_after_suspend, plugged_after_resume):
        """Suspends and resumes the DUT with different connections status
        before suspend, after suspend, and after resume

        @param plugged_before_suspend: a boolean, plugged before suspend
        @param plugged_after_suspend: a boolean, plugged after suspend
        @param plugged_after_resume: a boolean, plugged after resume

        """
        boot_id = self.host.get_boot_id()
        #Plug before suspend
        self.set_plug(plugged_before_suspend)
        time.sleep(self.WAIT_TIME)
        logging.debug('Going to suspend, for %d seconds...',
                     self.SUSPEND_DURATION)
        time_before_suspend = time.time()
        self.display_facade.suspend_resume_bg(self.SUSPEND_DURATION)

        # Confirm DUT suspended.
        self.host.test_wait_for_sleep(self.SUSPEND_TIMEOUT)
        self.set_plug(plugged_after_suspend)

        current_time = time.time()
        sleep_time = (self.SUSPEND_DURATION -
                      (current_time - time_before_suspend))
        logging.debug('Wait for %.2f seconds...', sleep_time)
        time.sleep(sleep_time)

        self.host.test_wait_for_resume(boot_id, self.RESUME_TIMEOUT)
        logging.debug('Resumed ')

        self.set_plug(plugged_after_resume)


    def wait_to_suspend(self, suspend_timeout):
        """Wait for DUT to suspend.

        @param suspend_timeout: Time in seconds to wait for suspend

        @exception TestFail: If fail to suspend in time
        """
        if not self.host.ping_wait_down(timeout=suspend_timeout):
            raise error.TestFail('Failed to SUSPEND after %d seconds' %
                                 suspend_timeout)

        logging.debug('Dut is suspended.')

    def wait_to_resume(self, resume_timeout):
        """Wait for DUT to resume.

        @param resume_timeout: Time in seconds to wait for resuming

        @exception TestFail: if fail to resume in time
        """
        if not self.host.wait_up(timeout=resume_timeout):
            raise error.TestFail(
                'Failed to RESUME after %d seconds' %
                    resume_timeout)
        logging.debug('Dut is up.')


    def check_external_display(self):
        """Display status check"""
        self.test_name = '%s-%s-%s' % (self.connector_used,
            str(self.resolution),
            'mirror' if self.test_mirrored else 'extended')
        #Check connector
        self.check_external_display_connector(self.connector_used)
        #Check test image
        self.load_test_image_and_check(
            self.test_name, self.resolution,
            under_mirrored_mode=self.test_mirrored,
            error_list=self.errors)
        #Check for crashes.
        if self.is_crash_data_present():
            self.errors.append('Crash data is detected on DUT')
        self.raise_on_errors(self.errors)

    def get_edids_filepaths(self):
        """Gets the EDID data files for the connector type used"""
        if self.connector_used.startswith('HDMI'):
            first_edid,second_edid = self.EDID_FILE_NAMES[0]
        elif self.connector_used.startswith('DP'):
            first_edid,second_edid = self.EDID_FILE_NAMES[1]
        first_edid = os.path.join(self.bindir, 'test_data/edids', first_edid)
        second_edid = os.path.join(self.bindir, 'test_data/edids', second_edid)
        return (first_edid, second_edid)


    def reconnect_and_get_external_resolution(self):
        """Reconnect the display and get the external screen resolution."""
        self.reconnect_output()
        #Get the resolution for the edid applied
        self.resolution = self.chameleon_port.get_resolution()
        logging.debug('External display resolution: %s',
                str(self.resolution))


    def apply_edid_and_reconnect(self, edid_file, suspended=False):
        """Apply EDID from a file

        @param edid_file: file path to edid data
        @param suspended: a boolean, to not reconnect ouptut when suspended

        """
        self.apply_edid_file(edid_file)
        #reconnect for the new edid if not suspended
        if not suspended:
            self.reconnect_and_get_external_resolution()

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

        #Remove any crash data before test procedure
        if self.is_crash_data_present():
            self.remove_crash_data()

        self.connector_used = self.display_facade.get_external_connector_name()
        first_edid, second_edid = self.get_edids_filepaths()

        #Set first monitor/EDID and tracked resolution
        self.apply_edid_and_reconnect(first_edid)
        #Set main display mode for the test
        self.set_mirrored(self.test_mirrored)

        #Reboot the device as connected and login
        self.reboot_device(plugged_before=True, plugged_after=True)
        #Check status
        self.check_external_display()

        #Dock and undock (close lid and open lid)
        if self.dock_dut():
            self.undock_dut();

        #Switch mode
        self.switch_display_mode()
        #Switch mode back
        self.switch_display_mode()
        self.check_external_display()

        #Suspend and resume as currently plugged
        self.suspend_resume()

        #Unplug-Suspend-Plug-Resume
        self.suspend_resume(plugged_before_suspend=False,
                               plugged_after_suspend=True,
                               plugged_after_resume=True)
        #Check status
        self.check_external_display()

        #Switch mode
        self.switch_display_mode()
        #Switch mode back
        self.switch_display_mode()

        #Suspens-Unplug-Resume-Plug
        self.suspend_resume(plugged_before_suspend=True,
                               plugged_after_suspend=False,
                               plugged_after_resume=True)
        #Check status
        self.check_external_display()

        #Docked mode(close lid)
        if self.dock_dut():
            logging.debug('Unplug display')
            #Unplug, thus DUT should suspend
            self.set_plug(False)
            self.wait_to_suspend(self.SUSPEND_TIMEOUT)
            logging.debug('DUT is suspended')

        #Plug the second monitor while suspended
        self.apply_edid_and_reconnect(second_edid, suspended=True)
        #Plug back
        self.set_plug(True)

        #Resume(open lid), doesn't hurt if DUT is not docked
        self.undock_dut()
        self.wait_to_resume(self.RESUME_TIMEOUT)

        self.reconnect_and_get_external_resolution()
        #Check status
        self.check_external_display()

        #Switch mode
        self.switch_display_mode()
        #Switch mode back
        self.switch_display_mode()

        #Unplug and plug the original monitor
        self.set_plug(False)
        self.apply_edid_and_reconnect(first_edid)
        self.set_plug(True)
        self.check_external_display()

