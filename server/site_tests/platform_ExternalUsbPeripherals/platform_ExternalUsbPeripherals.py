# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re, threading, time

from autotest_lib.server import autotest, test
from autotest_lib.server.cros import stress
from autotest_lib.client.common_lib import error, site_utils

_WAIT_DELAY = 10
_SUSPEND_RESUME_TIMEOUT = 200
_UNSUPPORTED_GBB_BOARDS = ['x86-mario', 'x86-alex', 'x86-zgb']
_SUSPEND_RESUME_BOARDS = ['daisy', 'panther']
_LOGIN_TIMEOUT_MESSAGE = 'DEVICE DID NOT LOGIN IN TIME!'

class platform_ExternalUsbPeripherals(test.test):
    """Uses servo to repeatedly connect/remove USB devices during boot."""
    version = 1


    def getPluggedUsbDevices(self):
        """Determines the external USB devices plugged

        @returns plugged_list: List of plugged usb devices names

        """
        lsusb_output = self.host.run('lsusb').stdout.strip()
        items = lsusb_output.split('\n')
        plugged_list = []
        unnamed_device_count = 1
        for item in items:
            columns = item.split(' ')
            if len(columns) == 6 or len(' '.join(columns[6:]).strip()) == 0:
                logging.debug('Unnamed device located, adding generic name.')
                name = 'Unnamed device %d' % unnamed_device_count
                unnamed_device_count += 1
            else:
                name = ' '.join(columns[6:]).strip()
            plugged_list.append(name)
        return plugged_list


    def set_hub_power(self, on=True):
        """Setting USB hub power status

        @param on: To power on the servo-usb hub or not

        """
        reset = 'off'
        if not on:
            reset = 'on'
        self.host.servo.set('dut_hub1_rst1', reset)
        self.pluged_status = on

    def action_login(self):
        """Login i.e. start running client test"""
        self.autotest_client.run_test(
            self.client_autotest,
            exit_without_logout=self.exit_without_logout)


    def action_logout(self):
        """Logout i.e. stop the client test."""
        client_termination_file_path = '/tmp/simple_login_exit'
        self.host.run('touch %s' % client_termination_file_path)


    def wait_to_suspend(self, suspend_timeout):
        """Wait for DUT to suspend.

        @param resume_timeout: Time in seconds to wait for suspend

        @exception TestFail  if fail to suspend in time
        @returns time took to suspend
        """
        start_time = int(time.time())
        if not self.host.ping_wait_down(timeout=suspend_timeout):
            raise error.TestFail(
                'Failed to SUSPEND after %d seconds' %
                    suspend_timeout)
        return int(time.time()) - start_time


    def wait_to_resume(self, resume_timeout):
        """Wait for DUT to resume.

        @param resume_timeout: Time in seconds to wait for resuming

        @exception TestFail  if fail to resume in time
        @returns time took to resume
        """
        start_time = int(time.time())
        if not self.host.wait_up(timeout=resume_timeout):
            raise error.TestFail(
                'Failed to RESUME after %d seconds' %
                    resume_timeout)
        return int(time.time()) - start_time


    def wait_for_cmd_output(self, cmd, check, timeout, timeout_msg):
        """Waits till command output is meta

        @param cmd: executed command
        @param check: string to be checked for in cmd output
        @param timeout: max time in sec to wait for output
        @param timeout_msg: timeout failure message

        @returns True if check is found in command output; False otherwise
        """
        start_time = int(time.time())
        time_delta = 0
        while True:
            out = self.host.run(cmd, ignore_status=True).stdout.strip()
            if len(re.findall(check, out)) > 0:
                break
            time_delta = int(time.time()) - start_time
            if time_delta > timeout:
                 self.fail_reasons.append('%s - %d sec'
                                          % (timeout_msg, timeout))
                 return False
            time.sleep(0.5)
        return True


    def wait_to_login(self):
        """Waits untill the user is logged

        @exception TestFail failed to login within timeout.
        """
        login_result = self.wait_for_cmd_output('cryptohome --action=status',
            '"mounted": true', _WAIT_DELAY * 4, _LOGIN_TIMEOUT_MESSAGE)
        if login_result:
            logging.debug('Successfully loged-in.')
        else:
            raise error.TestFail(_LOGIN_TIMEOUT_MESSAGE)


    def action_suspend(self):
        """Suspend i.e. close lid"""
        self.host.servo.lid_close()
        stime = self.wait_to_suspend(_SUSPEND_RESUME_TIMEOUT)
        self.suspend_status = True
        logging.debug('--- Suspended in %d sec' % stime)



    def action_resume(self):
        """Resume i.e. open lid"""
        self.host.servo.lid_open()
        rtime = self.wait_to_resume(_SUSPEND_RESUME_TIMEOUT)
        self.suspend_status = False
        logging.debug('--- Resumed in %d sec' % rtime)


    def powerd_suspend_with_timeout(self, timeout):
        """Suspend the device with wakeup alarm

        @param timeout: Wait time for the suspend wakealarm

        """
        self.host.run('echo 0 > /sys/class/rtc/rtc0/wakealarm')
        self.host.run('echo +%d > /sys/class/rtc/rtc0/wakealarm' % timeout)
        self.host.run('powerd_dbus_suspend --delay=0 &')


    def suspend_action_resume(self, action):
        """suspends and resumes through powerd_dbus_suspend in thread.

        @param action: Action while suspended

        """

        # Suspend and wait to be suspended
        logging.info('--- SUSPENDING')
        thread = threading.Thread(target = self.powerd_suspend_with_timeout,
                                  args = (_SUSPEND_RESUME_TIMEOUT,))
        thread.start()
        self.wait_to_suspend(_SUSPEND_RESUME_TIMEOUT)

        # Execute action after suspending
        do_while_suspended = re.findall(r'SUSPEND(\w*)RESUME', action)[0]
        plugged_list = self.on_list
        logging.info('--- %s-ing' % do_while_suspended)
        if do_while_suspended =='_UNPLUG_':
            self.set_hub_power(False)
            plugged_list = self.off_list
        elif do_while_suspended =='_PLUG_':
            self.set_hub_power(True)

        # Press power key and resume ( and terminate thread)
        logging.info('--- RESUMING')
        self.host.servo.power_key(0.1)
        self.wait_to_resume(_SUSPEND_RESUME_TIMEOUT)
        if thread.is_alive():
            raise error.TestFail('SUSPEND thread did not terminate!')


    def crash_not_detected(self, crash_path):
        """Check for kernel, browser, process crashes

        @param crash_path: Crash files path

        @returns True if there were not crashes; False otherwise
        """
        result = True
        if str(self.host.run('ls %s' % crash_path)).find('crash') != -1:
            crash_out = self.host.run('ls %s/crash/' % crash_path).stdout
            crash_files = crash_out.strip().split('\n')
            for crash_file in crash_files:
                if crash_file.find('.meta') != -1 and \
                    crash_file.find('kernel_warning') == -1:
                    self.fail_reasons.append('CRASH DETECTED in %s/crash: %s' %
                                             (crash_path, crash_file))
                    result = False
        return result


    def check_plugged_usb_devices(self):
        """Checks the plugged peripherals match device list.

        @returns True if expected USB peripherals are detected; False otherwise
        """
        result = True
        if self.pluged_status and self.usb_list != None:
            # Check for mandatory USb devices passed by usb_list flag
            for usb_name in self.usb_list:
                found = self.wait_for_cmd_output(
                    'lsusb', usb_name, _WAIT_DELAY * 3,
                    'Not detecting %s' % usb_name)
                result = result and found
        if self.pluged_status:
            dev_list = self.on_list
        else:
            dev_list = self.off_list
        time.sleep(_WAIT_DELAY)
        on_now = self.getPluggedUsbDevices( )
        if not len(set(dev_list).difference(set(on_now))) == 0:
            self.fail_reasons.append('The list of connected peripherals '
                                     'is wrong. --- Now: %s --- Should be: '
                                     '%s' % (on_now, dev_list))
            result = False
        return result


    def check_usb_peripherals_details(self):
        """Checks the effect from plugged in USB peripherals.

        @returns True if command line output is matched successfuly; Else False
        """
        usb_check_result = True
        for cmd in self.usb_checks.keys():
            out_match_list = self.usb_checks.get(cmd)
            if cmd.startswith('loggedin:'):
                if not self.login_status:
                    continue
                cmd = cmd.replace('loggedin:','')
            # Run the usb check command
            for out_match in out_match_list:
                match_result = self.wait_for_cmd_output(
                    cmd, out_match, _WAIT_DELAY * 3,
                    'USB CHECKS DETAILS failed at %s:' % cmd)
                usb_check_result = usb_check_result and match_result
        return usb_check_result


    def check_status(self):
        """Performs checks after each action:
            - for USB detected devices
            - for generated crash files
            - peripherals effect checks on cmd line

        @returns True if all of the iteration checks pass; False otherwise.
        """
        result = True
        if not self.suspend_status:
            # Detect the USB peripherals
            result = self.check_plugged_usb_devices()
            # Check for crash files
            crash_result = (self.crash_not_detected('/var/spool/') and
                self.crash_not_detected('/home/chronos/u*/') and
                self.crash_not_detected('/home/chronos/'))
            result = result and crash_result
            if self.pluged_status and (self.usb_checks != None):
                # Check for plugged USB devices details
                usb_check_result = self.check_usb_peripherals_details()
                result = result and usb_check_result
        return result


    def change_suspend_resume(self, actions):
        """ Modifying actions to suspend and resume

        Changes suspend and resume actions done with lid_close
        to suspend_resume done with powerd_dbus_suspend

        @returns The changed to suspend_resume action_sequence
        """
        susp_resumes = re.findall(r'(SUSPEND,\w*,*RESUME)',actions)
        for susp_resume in susp_resumes:
            replace_with = susp_resume.replace(',', '_')
            actions = actions.replace(susp_resume, replace_with, 1)
        return actions


    def run_once(self, host, client_autotest, action_sequence, repeat,
                 usb_list=None, usb_checks=None):
        self.client_autotest = client_autotest
        self.host = host
        self.autotest_client = autotest.Autotest(self.host)
        self.usb_list = usb_list
        self.usb_checks = usb_checks

        self.suspend_status = False
        self.login_status = False
        self.exit_without_logout = False
        self.fail_reasons = []
        skipped_gbb = False

        self.host.servo.switch_usbkey('dut')
        self.host.servo.set('usb_mux_sel3', 'dut_sees_usbkey')

        # Collect USB peripherals when unplugged
        self.set_hub_power(False)
        time.sleep(_WAIT_DELAY)
        self.off_list = self.getPluggedUsbDevices()

        # Collect USB peripherals when plugged
        self.set_hub_power(True)
        time.sleep(_WAIT_DELAY*2)
        self.on_list = self.getPluggedUsbDevices()

        diff_list = set(self.on_list).difference(set(self.off_list))
        if len(diff_list) == 0:
            # Fail if no devices detected after
            raise error.TestError('No connected devices were detected. Make '
                                  'sure the devices are connected to USB_KEY '
                                  'and DUT_HUB1_USB on the servo board.')
        logging.debug('Connected devices list: %s' % diff_list)

        skip_gbb = False
        board = host.get_board().split(':')[1]
        if board in _UNSUPPORTED_GBB_BOARDS:
            skip_gbb = True
        action_sequence = action_sequence.upper()
        if board in _SUSPEND_RESUME_BOARDS:
            action_sequence = self.change_suspend_resume(action_sequence)
        actions = action_sequence.split(',')
        for iteration in xrange(repeat):
            step = 0
            iteration += 1
            for action in actions:
                step += 1
                action = action.strip()
                action_step = '--- %d.%d. %s---' % (iteration, step, action)
                logging.info(action_step)

                if action == 'RESUME':
                    self.action_resume()
                elif action == 'UNPLUG':
                    self.set_hub_power(False)
                elif action == 'PLUG':
                    self.set_hub_power(True)
                elif self.suspend_status == False:
                    if action.startswith('LOGIN'):
                        if self.login_status == True:
                            logging.debug('Skipping login. Already logged in.')
                            continue
                        else:
                            if action =='LOGIN_EXIT':
                                self.exit_without_logout = True
                            stressor = stress.ControlledStressor(
                                self.action_login)
                            stressor.start()
                            self.wait_to_login()
                            if action =='LOGIN_EXIT':
                                stressor.stop()
                            self.login_status = True
                    elif action == 'LOGOUT':
                        if self.login_status == False:
                            logging.debug('Skipping. Already logged out.')
                            continue
                        else:
                            self.action_logout()
                            logging.debug('--- Logged out.')
                            stressor.stop()
                            self.login_status = False
                    elif action == 'REBOOT':
                        if self.login_status == True:
                            self.action_logout()
                            stressor.stop()
                            logging.debug('---Logged out.')
                            self.login_status = False
                        # We want fast boot past the dev screen
                        if not skip_gbb and not skipped_gbb:
                            self.host.run('/usr/share/vboot/bin/'
                                        'set_gbb_flags.sh 0x01')
                            skipped_gbb = True
                        self.host.reboot()
                    elif action == 'SUSPEND':
                        self.action_suspend()
                    elif re.match(r'SUSPEND\w*RESUME',action) is not None:
                        self.suspend_action_resume(action)
                else:
                    raise error.TestError('--- WRONG ACTION: %s ---.' %
                                          action_step)

                if not self.check_status():
                    raise error.TestFail('Step %s failed with: %s' %
                                         (action_step, str(self.fail_reasons)))

        if self.login_status and self.exit_without_logout == False:
            self.action_logout()
            logging.debug('--- Logged out.')
            stressor.stop()