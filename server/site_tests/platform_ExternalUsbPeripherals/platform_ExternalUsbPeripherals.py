# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re, threading, time

from autotest_lib.server import autotest, test
from autotest_lib.server.cros import stress
from autotest_lib.client.common_lib import error, site_utils

_WAIT_DELAY = 10
_SUSPEND_RESUME_TIMEOUT = 200
_SUSPEND_RESUME_BOARDS = ['daisy', 'panther']
_LOGIN_FAILED = 'DEVICE COULD NOT LOGIN!'
_SUSPEND_FAILED = 'Failed to SUSPEND within timeout'
_RESUME_FAILED = 'Failed to RESUME within timeout'
_CRASH_PATHS = ['/var/spool',
                '/home/chronos',
                '/home/chronos/u*']
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


    def is_logged_in(self):
        """Checks if DUT is logged"""
        out = self.host.run('ls /home/chronos/user/',
                            ignore_status=True).stdout.strip()
        if len(re.findall('Downloads', out)) > 0:
            return True
        return False


    def action_login(self):
        """Login i.e. runs running client test

        @exception TestFail failed to login within timeout.

        """
        self.autotest_client.run_test(self.client_autotest,
                                      exit_without_logout=True)
        if not self.is_logged_in():
            raise error.TestFail(_LOGIN_FAILED)


    def wait_to_disconnect(self, fail_msg, suspend_timeout):
        """Wait for DUT to suspend.

        @param fail_msg: Failure message
        @param resume_timeout: Time in seconds to wait to disconnect

        @exception TestFail  if fail to disconnect in time
        @returns time took to disconnect
        """
        start_time = int(time.time())
        if not self.host.ping_wait_down(timeout=suspend_timeout):
            raise error.TestFail(fail_msg)
        return int(time.time()) - start_time


    def wait_to_come_up(self, fail_msg, resume_timeout):
        """Wait for DUT to resume.

        @param fail_msg: Failure message
        @param resume_timeout: Time in seconds to wait to come up

        @exception TestFail  if fail to come_up in time
        @returns time took to come up
        """
        start_time = int(time.time())
        if not self.host.wait_up(timeout=resume_timeout):
            raise error.TestFail(fail_msg)
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


    def action_suspend(self):
        """Suspend i.e. close lid"""
        self.host.servo.lid_close()
        stime = self.wait_to_disconnect(_SUSPEND_FAILED,
                                        _SUSPEND_RESUME_TIMEOUT)
        self.suspend_status = True
        logging.debug('--- Suspended in %d sec' % stime)



    def action_resume(self):
        """Resume i.e. open lid"""
        self.host.servo.lid_open()
        rtime = self.wait_to_come_up(_RESUME_FAILED, _SUSPEND_RESUME_TIMEOUT)
        self.suspend_status = False
        logging.debug('--- Resumed in %d sec' % rtime)


    def action_reboot(self):
        """Reboot DUT"""
        boot_id = self.host.get_boot_id()
        self.host.reboot(wait=False)
        self.host.test_wait_for_shutdown()
        self.host.test_wait_for_boot(boot_id)


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
        self.wait_to_disconnect(_SUSPEND_RESUME_TIMEOUT)

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
        self.wait_to_come_up(_RESUME_FAILED, _SUSPEND_RESUME_TIMEOUT)
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
        on_now = self.getPluggedUsbDevices()
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
            for crash_path in _CRASH_PATHS:
                result = result and self.crash_not_detected(crash_path)
            if self.pluged_status and (self.usb_checks != None):
                # Check for plugged USB devices details
                result = result and self.check_usb_peripherals_details()
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


    def remove_crash_data(self):
        """Delete crash meta files"""
        for crash_path in _CRASH_PATHS:
            if not self.crash_not_detected(crash_path):
                self.host.run('rm -rf %s/crash' % crash_path,
                              ignore_status=True)


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

        board = host.get_board().split(':')[1]
        action_sequence = action_sequence.upper()
        if board in _SUSPEND_RESUME_BOARDS:
            action_sequence = self.change_suspend_resume(action_sequence)
        actions = action_sequence.split(',')
        self.remove_crash_data()
        for iteration in xrange(1, repeat + 1):
            step = 0
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
                        if self.is_logged_in():
                            logging.debug('Skipping login. Already logged in.')
                            continue
                        else:
                            self.action_login()
                            self.login_status = True
                    elif action == 'REBOOT':
                        self.action_reboot()
                        self.login_status = False
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
