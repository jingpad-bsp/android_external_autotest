# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json, logging, os, pwd, shutil, subprocess, time

import dbus

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import semiauto_framework
from autotest_lib.client.cros import sys_power
from telemetry.core import util

_USER_TIMEOUT_TIME = 321  # Seconds a tester has to respond to prompts
_DEVICE_TIMEOUT_TIME = 321  # Seconds a tester has to pair or connect device
_ADAPTER_INTERFACE = 'org.bluez.Adapter1' # Name of adapter in DBus interface
_DEVICE_INTERFACE = 'org.bluez.Device1' # Name of a device in DBus interface
_TIME_FORMAT = '%d %b %Y %H:%M:%S' # Human-readable time format for logs
_SECTION_BREAK = '='*75


class BluetoothSemiAutoHelper(semiauto_framework.semiauto_test):
    """Generic Bluetooth SemiAutoTest.

    Contains functions needed to implement an actual Bluetooth SemiAutoTest,
    such as accessing the state of Bluetooth adapter/devices via dbus,
    opening dialogs with tester via Telemetry browser, and getting log data.
    """
    version = 1

    def _err(self, message):
        """Raise error after first collecting more information."""
        self.collect_logs('ERROR HAS OCCURED: %s' % message)
        raise error.TestError(message)

    def _get_objects(self):
        manager = dbus.Interface(
                self._bus.get_object('org.bluez', '/'),
                dbus_interface='org.freedesktop.DBus.ObjectManager')
        return manager.GetManagedObjects()

    def _get_adapter_properties(self):
        objects = self._get_objects()
        for _, interfaces in objects.items():
            if _ADAPTER_INTERFACE in interfaces:
                return interfaces[_ADAPTER_INTERFACE]
        self._err('Bluetooth Adapter not found')

    def _get_device_properties(self, addr):
        objects = self._get_objects()
        for _, interfaces in objects.items():
            if _DEVICE_INTERFACE in interfaces:
                if interfaces[_DEVICE_INTERFACE]['Address'] == addr:
                    return interfaces[_DEVICE_INTERFACE]
        return None

    def _verify_adapter(self, adapter_status=True):
        """Return True/False if adapter status matches given value."""
        properties = self._get_adapter_properties()
        return True if properties['Powered'] == adapter_status else False

    def _verify_connection(self, addr, paired_status=True,
                           connected_status=True):
        """Return True/False if device statuses match given values."""
        def _check_properties():
            properties = self._get_device_properties(addr)
            if properties:
                if (properties['Paired'] != paired_status or
                    properties['Connected'] != connected_status):
                    return False
                return True
            # Return True if no entry was found for an unpaired device
            return not paired_status and not connected_status

        results = _check_properties()

        # To avoid spotting brief connections, sleep and check again.
        if results:
            time.sleep(0.5)
            results = _check_properties()
        return results

    def wait_for_adapter(self, adapter_status=True):
        """Wait until adapter status matches given value.

        @param adapter_status: True for adapter is on; False off.
        """
        def _complete():
            return self._verify_adapter(adapter_status=adapter_status)
        try:
            util.WaitFor(_complete, _DEVICE_TIMEOUT_TIME, poll_interval=1)
        except:
            adapter_str = 'ON' if adapter_status else 'OFF'
            raise error.TestError(
                    'Timeout for Bluetooth Adapter to be %s' % adapter_str)

    def _wait_for_connection(self, addr, paired_status, connected_status):
        """Wait until device statuses match given values."""
        paired_str = 'PAIRED' if paired_status else 'NOT PAIRED'
        conn_str = 'CONNECTED' if connected_status else 'NOT CONNECTED'
        message = 'Waiting for device %s to be %s and %s' % (addr, paired_str,
                                                             conn_str)
        logging.info(message)

        def _complete():
            return self._verify_connection(addr, paired_status=paired_status,
                                           connected_status=connected_status)
        try:
            util.WaitFor(_complete, _DEVICE_TIMEOUT_TIME, poll_interval=1)
        except:
            self._err('Timeout while %s' % message)

    def wait_for_connections(self, paired_status=True, connected_status=True):
        """Wait until all Bluetooth devices have the given statues.

        @param paired_status: True for device paired; False for unpaired.
        @param connected_status: True for device connected; False for not.
        """
        for addr in self._addrs:
            self._wait_for_connection(addr, paired_status=paired_status,
                                      connected_status=connected_status)

    def login_and_open_browser(self):
        """Log in to machine, open browser, and navigate to dialog template.

        Assumes the existence of 'client/cros/audio/music.mp3' file, and will
        fail if not found.
        """
        # Open browser and interactive tab
        self.login_and_open_interactive_tab()

        # Find mounted home directory
        user_home = None
        for udir in os.listdir(os.path.join('/', 'home', 'user')):
            d = os.path.join('/', 'home', 'user', udir)
            if os.path.ismount(d):
                user_home = d
        if user_home is None:
            raise error.TestError('Could not find mounted home directory')

        # Setup Audio File
        audio_dir = os.path.join(self.bindir, '..', '..', 'cros', 'audio')
        loop_file = os.path.join(audio_dir, 'loop.html')
        music_file = os.path.join(audio_dir, 'music.mp3')
        dl_dir = os.path.join(user_home, 'Downloads')
        self._added_loop_file = os.path.join(dl_dir, 'loop.html')
        self._added_music_file = os.path.join(dl_dir, 'music.mp3')
        shutil.copyfile(loop_file, self._added_loop_file)
        shutil.copyfile(music_file, self._added_music_file)
        uid = pwd.getpwnam('chronos').pw_uid
        gid = pwd.getpwnam('chronos').pw_gid
        os.chmod(self._added_loop_file, 0755)
        os.chmod(self._added_music_file, 0755)
        os.chown(self._added_loop_file, uid, gid)
        os.chown(self._added_music_file, uid, gid)

        # Open Test Dialog tab, Settings tab, and Audio file
        self._settings_tab = self._browser.tabs.New()
        self._settings_tab.Navigate('chrome://settings/search#Bluetooth')
        music_tab = self._browser.tabs.New()
        music_tab.Navigate('file:///home/chronos/user/Downloads/loop.html')

    def ask_user(self, message):
        """Ask the user a yes or no question in an open tab.

        Reset dialog page to be a question (message param) with 'PASS' and
        'FAIL' buttons.  Wait for answer.  If no, ask for more information.

        @param message: string sent to the user via browswer interaction.
        """
        logging.info('Asking user "%s"', message)
        sandbox = 'SANDBOX:<input type="text"/>'
        html = '<h3>%s</h3>%s' % (message, sandbox)
        self.set_tab_with_buttons(html, buttons=['PASS', 'FAIL'])

        # Intepret results.
        result = self.wait_for_tab_result(timeout=_USER_TIMEOUT_TIME)
        if result == 1:
            # Ask for more information on error.
            html='<h3>Please provide more info:</h3>'
            self.set_tab_with_textbox(html)

            # Get explanation of error, clear output, and raise error.
            result = self.wait_for_tab_result(timeout=_USER_TIMEOUT_TIME)
            self.clear_output()
            self._err('Testing %s. "%s"' % (self._test_type, result))
        elif result != 0:
            raise error.TestError('Bad dialog value: %s' % result)
        logging.info('Answer was PASS')

        # Clear user screen.
        self.clear_output()

    def tell_user(self, message):
        """Tell the user the given message in an open tab.

        @param message: the text string to be displayed.
        """
        logging.info('Telling user "%s"', message)
        html = '<h3>%s</h3>' % message
        self.set_tab(html)

    def check_working(self, message=None):
        """Steps to check that all devices are functioning.

        Ask user to connect all devices, verify connections, and ask for
        user input if they are working.

        @param message: string of text the user is asked.  Defaults to asking
                        the user to connect all devices.
        """
        if not message:
            message = ('Please connect all devices.<br>(You may need to '
                       'click mice, press keyboard keys, or use the '
                       'Connect button in Settings.)')
        self.tell_user(message)
        self.wait_for_adapter(adapter_status=True)
        self.wait_for_connections(paired_status=True, connected_status=True)
        self.ask_user('Are all Bluetooth devices working?<br>'
                       'Is audio playing only through Bluetooth devices?<br>'
                       'Do onboard keyboard and trackpad work?')

    def ask_not_working(self):
        """Ask the user pre-defined message about NOT working."""
        self.ask_user('No Bluetooth devices work.<br>Audio is NOT playing '
                      'through onboard speakers or wired headphones.')

    def start_dump(self, message=''):
        """Run hcidump in subprocess.

        Kill previous hcidump (if needed) and start new one using current
        test type as base filename.  Dumps stored in results folder.

        @param message: string of text added to top of log entry.
        """
        if self._dump:
            self._dump.kill()
        logging.info('Starting hcidump')
        filename = '%s_hcidump' % self._test_type
        path = os.path.join(self.resultsdir, filename)
        with open(path, 'a') as f:
            f.write('%s\n' % _SECTION_BREAK)
            f.write('%s: Starting hcidump\n' % time.strftime(_TIME_FORMAT))
            f.write('%s\n' % message)
            f.flush()
            hcidump_path = '/usr/bin/hcidump'
            try:
                self._dump = subprocess.Popen([hcidump_path], stdout=f,
                                              stderr=subprocess.PIPE)
            except Exception as e:
                raise error.TestError('hcidump: %s' % e)

    def collect_logs(self, message=''):
        """Store results of dbus GetManagedObjects and hciconfig.

        Use current test type as base filename.  Stored in results folder.

        @param message: string of text added to top of log entry.
        """
        logging.info('Collecting dbus info')
        filename = '%s_dbus' % self._test_type
        path = os.path.join(self.resultsdir, filename)
        with open(path, 'a') as f:
            f.write('%s\n' % _SECTION_BREAK)
            f.write('%s: %s\n' % (time.strftime(_TIME_FORMAT), message))
            f.write(json.dumps(self._get_objects(), indent=2))
            f.write('\n')

        logging.info('Collecting hciconfig info')
        filename = '%s_hciconfig' % self._test_type
        path = os.path.join(self.resultsdir, filename)
        with open(path, 'a') as f:
            f.write('%s\n' % _SECTION_BREAK)
            f.write('%s: %s\n' % (time.strftime(_TIME_FORMAT), message))
            f.flush()
            hciconfig_path = '/usr/bin/hciconfig'
            try:
                subprocess.check_call([hciconfig_path, '-a'], stdout=f)
            except Exception as e:
                raise error.TestError('hciconfig: %s' % e)

    def os_idle_time_set(self, reset=False):
        """Function to set short idle time or to reset to normal.

        Not using sys_power so that user can use Bluetooth to wake machine.

        @param reset: true to reset to normal idle time, false for short.
        """
        powerd_path = '/usr/bin/set_short_powerd_timeouts'
        flag = '--reset' if reset else ''
        try:
            subprocess.check_call([powerd_path, flag])
        except Exception as e:
            raise error.TestError('idle cmd: %s' % e)

    def os_suspend(self):
        """Function to suspend ChromeOS using sys_power."""
        sys_power.do_suspend(5)

    def initialize(self):
        self._will_close_browser = True
        self._bus = dbus.SystemBus()
        self._dump = None
        self.login_and_open_browser()

    def warmup(self, addrs='', test_phase='client', close_browser=True):
        """Warmup setting paramters for semi-automated Bluetooth Test.

        Actual test steps are implemened in run_once() function.

        @param: addrs: list of MAC address of Bluetooth devices under test.
        @param: test_phase: for use by server side tests to, for example, call
                            the same test before and after a reboot.
        @param: close_browser: True if client side test should close browser
                               at end of test.
        """
        self._addrs = addrs
        self._test_type = 'start'
        self._test_phase = test_phase
        self._will_close_browser = close_browser

    def cleanup(self):
        """Cleanup of various files/processes opened during test.

        Closes running hcidump, closes browser (if asked to at start), and
        deletes files added during test.
        """
        if self._dump:
            self._dump.kill()
        if self._will_close_browser:
            self.close_browser()
        if os.path.exists(self._added_loop_file):
            os.remove(self._added_loop_file)
        if os.path.exists(self._added_music_file):
            os.remove(self._added_music_file)
