# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error

import dbus
import logging
import os
import re

'''A test verifying that the default bluetooth settings are correct.

Runs hciconfig on host and checks for expected output.
'''

class security_HciconfigDefaultSettings(test.test):
    version = 1

    def compare(self, received, expected):
        '''Compares two strings and logs results.

        Uses regular expression matching to compare whitespace-stripped received
        output to whitespace-stripped expected output and uses logging.debug to
        record findings.

        Args:
            received: String output received.
            expected: String output expected (regular expression).

        Returns:
            True if strings match, False otherwise.
        '''
        logging.debug('Expecting: %s' % expected.strip())
        if not re.search(expected.strip(), received.strip()):
            logging.debug('No match, saw: %s' % received.strip())
            return False
        logging.debug('Match found.')
        return True

    def get_adapter(self):
        '''Gets adapter interface for bluetooth through D-Bus.

        Uses dbus to get the name of the default adapter for BlueZ, then uses
        dbus to get an interface to that adapter.

        Returns:
            A dbus interface object referencing the default BlueZ adapter.
        '''
        bus = dbus.SystemBus()
        default = bus.get_object('org.bluez', '/')
        adapter_path = default.DefaultAdapter(dbus_interface=
                'org.bluez.Manager')

        adapter_proxy = bus.get_object('org.bluez', adapter_path)
        adapter = dbus.Interface(adapter_proxy, dbus_interface=
                'org.bluez.Adapter')
        return adapter

    def set_adapter_power(self, adapter, state):
        '''Sets adapter 'Powered' property to desired state

        Uses interface provided by dbus to change adapter's property

        Args:
            adapter: adapter to modify
            state: desired state (True for enabled, False for disabled)
        '''
        logging.debug('Powering adapter %s.' % ('off', 'on')[state])
        adapter.SetProperty('Powered', state)

    def verify_settings(self):
        '''Checks all required default settings.

        Runs hciconfig command, parses output, and makes sure that bluetooth is
        enabled, running PSCAN, and not running ISCAN.

        Returns:
            True if all settings are correct, False otherwise.
        '''
        output = utils.system_output('hciconfig -a').splitlines()

        only_pscan = self.compare(output[2], 'UP RUNNING PSCAN$')

        return only_pscan

    def run_once(self):
        '''Main function.

        Runs hciconfig command on host, checks output. Fails if it does not
        match expected setting values.

        Raises:
            error.TestError if more than one Bluetooth interface is found.
            error.TestFail if settings don't match expected values.
        '''
        output = utils.system_output('hciconfig -a').splitlines()
        num_lines = len(output)
        if num_lines == 0:
            logging.debug('No bluetooth functionality present, exiting.')
            return
        # Expect 9 lines of output for one down interface and 16 lines of
        # output for one up interface.
        if num_lines != 9 and num_lines != 16:
            logging.debug(output)
            raise error.TestError('Unexpected quantity of Bluetooth interface'
                    'information.  Expected 9 or 16 lines, saw %d:' % lines)

        was_down = self.compare(output[2], 'DOWN')

        adapter = self.get_adapter()

        if was_down:
            self.set_adapter_power(adapter, True)

        good_settings = self.verify_settings()

        if was_down:
            self.set_adapter_power(adapter, False)

        if not was_down:
            raise error.TestFail('Bluetooth was already up.')
        if not good_settings:
            raise error.TestFail('One or more Bluetooth settings did not match '
                           'expected default values.')
