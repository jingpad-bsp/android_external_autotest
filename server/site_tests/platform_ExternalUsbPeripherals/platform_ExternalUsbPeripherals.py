# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, re, threading, time

from autotest_lib.server import autotest, test
from autotest_lib.server.cros import stress
from autotest_lib.client.common_lib import error, site_utils

_WAIT_DELAY = 7
_UNSUPPORTED_GBB_BOARDS = ['x86-mario', 'x86-alex', 'x86-zgb']

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
        time.sleep(_WAIT_DELAY)
        self.pluged_status = on


    def action_login(self):
        """Login i.e. start running client test"""
        logging.debug('--- Initiate login.')
        self.autotest_client.run_test(self.client_autotest)


    def action_logout(self):
        """Logout i.e. stop the client test."""
        client_termination_file_path = '/tmp/simple_login_exit'
        logging.debug('--- Initiate logout.')
        self.host.run('touch %s' % client_termination_file_path)


    def action_suspend(self):
        """Suspend i.e. close lid"""
        logging.debug('--- Initiate suspend')
        self.host.servo.lid_close()
        time.sleep(_WAIT_DELAY * 2)
        logging.debug('--- Suspended')


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
        logging.debug('--- SUSPENDING')
        thread = threading.Thread(target = self.powerd_suspend_with_timeout,
                                  args = ( _WAIT_DELAY * 3,))
        thread.start()
        time.sleep(_WAIT_DELAY)
        do_while_suspended = re.findall(r'SUSPEND(\w*)RESUME',action)[0]
        plugged_list = self.on_list

        # Execute action before suspending
        if do_while_suspended =='_UNPLUG_':
            self.action_unplug()
            plugged_list = self.off_list
        elif do_while_suspended =='_PLUG_':
            self.action_plug()
        logging.debug('--- %s DONE' % do_while_suspended)

        # Terminate thread and resume
        thread.join()
        if thread.is_alive():
            logging.debug('SUSPEND not terminated. Trying again.')
            thread.join()
        logging.debug('--- RESUMED')
        time.sleep(_WAIT_DELAY)
        self.check_plugged_devices(action)


    def action_resume(self):
        """Resume i.e. open lid"""
        logging.debug('--- Initiate resume')
        self.host.servo.lid_open()
        time.sleep(_WAIT_DELAY * 2)
        logging.debug('--- Resumed')


    def action_unplug(self):
        """Unplug the USB i.e. hub power off"""
        logging.debug('--- Initiate unplug.')
        self.set_hub_power(False)
        time.sleep(_WAIT_DELAY)


    def action_plug (self):
        """Plug the USB i.e. hub power on"""
        logging.debug('--- Initiate plug.')
        self.set_hub_power(True)
        time.sleep(_WAIT_DELAY)


    def action_reboot(self):
        """Rebooting the DUT."""
        logging.debug('--- Initiate reboot.')
        self.host.reboot()
        logging.debug('--- Reboot complete.')


    def action_wait(self):
        """Wait for five seconds."""
        logging.debug('--- WAITING for 5 sec ---')
        time.sleep(_WAIT_DELAY)


    def crash_check(self, crash_path):
        """Check for kernel, browser, process crashes

        @param: crash_path: Crash files path

        """
        if str(self.host.run('ls %s' % crash_path)).find('crash') != -1:
            crash_files = str(self.host.run('ls %s/crash/' % crash_path))
            if crash_files.find('.meta') != -1:
                 logging.debug('CRASH DETECTED in %s/crash \n %s' %
                                (crash_path, crash_files))
                 return False
        return True


    def check_plugged_devices(self, action_name):
        """Checks the plugged peripherals match device list.

        @param: action_name: Action string to output if failure
        """
        on_now = self.getPluggedUsbDevices()
        if self.pluged_status:
            dev_list = self.on_list
        else:
            dev_list = self.off_list
        if not len(set(dev_list).difference(set(on_now))) == 0:
            raise error.TestFail('The list of connected items after %s is '
                                 'wrong. --- Now: %s --- Should be: %s' %
                                 (action_name, on_now, dev_list))


    def check_usb_peripherals_details(self):
        """Checks the effect from plugged in USB peripherals.

        @returns True if command line output is matched successfuly; Else False
        """
        usb_check_result = True
        for cmd in self.usb_checks.keys():
            out_match_list = self.usb_checks.get(cmd)
            # Run the usb check command
            cmd_out_lines = self.host.run(cmd).stdout.strip().split('\n')
            for out_match in out_match_list:
                match_result = False
                for cmd_out_line in cmd_out_lines:
                    match_result = (match_result or
                        re.search(out_match, cmd_out_line) != None)
                if not match_result:
                    logging.debug('USB CHECKS details failed at %s: %s\n'
                                 'Should be matching %s' %
                                 (cmd, cmd_out_line, out_match))
                usb_check_result = usb_check_result and match_result
        return usb_check_result


    def check_status(self):
        """Performs checks after each iteration:
            - for generated crash files
            - for device disconnected while suspended
            - peripherals effect checks on cmd line

        @returns True if all of the iteration checks pass; False otherwise.
        """
        if not self.suspend_status:
            # Check for crash files
            result = (self.crash_check('/var/spool/') or
                self.crash_check('/home/chronos/u*/') or
                self.crash_check('/home/chronos/'))
            if all([self.login_status, self.pluged_status,
                   (self.usb_checks != None)]):
                # Check for plugged USB devices details
                result = result and self.check_usb_peripherals_details()
        else:
            # Device should not be pingabe.
            result = (site_utils.ping(self.host.ip, deadline = 2) != 0)
        return result


    def run_once(self, host, client_autotest,
                 action_sequence, repeat, usb_checks = None):
        self.client_autotest = client_autotest
        self.host = host
        self.autotest_client = autotest.Autotest(self.host)
        self.usb_checks = usb_checks

        self.suspend_status = False
        self.login_status = False
        skipped_gbb = False
        usb_details_check = True
        final_result = True
        failed_steps = []

        self.host.servo.switch_usbkey('dut')
        self.host.servo.set('usb_mux_sel3', 'dut_sees_usbkey')

        # Collect devices when unplugged
        self.set_hub_power(False)
        self.off_list = self.getPluggedUsbDevices()

        # Collect devices when plugged
        self.set_hub_power(True)
        self.on_list = self.getPluggedUsbDevices()

        diff_list = set(self.on_list).difference(set(self.off_list))
        if len(diff_list) == 0:
            # Fail if no devices detected after
            raise error.TestError('No connected devices were detected. Make '
                                  'sure the devices are connected to USB_KEY '
                                  'and DUT_HUB1_USB on the servo board.')
        logging.debug('Connected devices list: %s' % diff_list)

        lsb_release = self.host.run('cat /etc/lsb-release').stdout.split('\n')
        skip_gbb = False
        for line in lsb_release:
            m = re.match(r'^CHROMEOS_RELEASE_BOARD=(.+)$', line)
            if m and m.group(1) in _UNSUPPORTED_GBB_BOARDS:
                skip_gbb = True
                break

        actions = action_sequence.upper().split(',')
        for iteration in xrange(repeat):
            step = 0
            iteration += 1
            for action in actions:
                step += 1
                action = action.strip()
                action_step = '--- %d.%d. %s---' % (iteration, step, action)
                logging.debug(action_step)

                if action == 'LOGIN' and self.suspend_status == False:
                    if self.login_status == True:
                        logging.debug('Skipping login. Already logged in.')
                    else:
                        stressor = stress.ControlledStressor(self.action_login)
                        stressor.start()
                        time.sleep(3 * _WAIT_DELAY)
                        logging.debug('--- Logged in.')
                        self.login_status = True
                elif action == 'LOGOUT' and self.suspend_status == False:
                    if self.login_status == False:
                        logging.debug('Skipping logout. Already logged out.')
                    else:
                        self.action_logout()
                        logging.debug('--- Logged out.')
                        stressor.stop()
                        self.login_status = False
                elif action == 'REBOOT' and self.suspend_status == False:
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
                    self.action_reboot()
                elif action == 'SUSPEND' and self.suspend_status == False:
                    self.action_suspend()
                    self.suspend_status = True
                elif re.match(r'SUSPEND\w*RESUME',action) is not None and \
                    self.suspend_status == False:
                    self.suspend_action_resume(action)
                elif action == 'RESUME':
                    self.action_resume()
                    self.suspend_status = False
                    self.check_plugged_devices(action)
                elif action == 'WAIT':
                    self.action_wait()
                elif action == 'UNPLUG':
                    self.action_unplug()
                    if self.suspend_status == False:
                        self.check_plugged_devices(action)
                elif action == 'PLUG':
                    self.action_plug()
                    if self.suspend_status == False:
                        self.check_plugged_devices(action)
                else:
                    raise error.TestError('--- WRONG ACTION: %s ---.' %
                                          action_step)
                step_result = self.check_status()

                if not step_result:
                    failed_steps.append(action_step)
                final_result = (final_result and step_result)

        if self.login_status == True:
            self.action_logout()
            stressor.stop()
            time.sleep(_WAIT_DELAY)

        if final_result == False:
            raise error.TestFail('TEST CHECKS FAILED! %s' % str(failed_steps))
