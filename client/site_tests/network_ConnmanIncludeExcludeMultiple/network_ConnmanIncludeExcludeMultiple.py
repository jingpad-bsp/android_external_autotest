# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import utils
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

import dbus, subprocess, time

class network_ConnmanIncludeExcludeMultiple(test.test):
    version = 1
    connman_path = 'org.chromium.flimflam'


    def get_interfaces(self):
        bus = dbus.SystemBus()
        connman = bus.get_object(self.connman_path, '/')
        connman_props = connman.GetProperties(
            dbus_interface='org.chromium.flimflam.Manager')
        interfaces = []
        for device in connman_props['Devices']:
            device_obj = bus.get_object(self.connman_path, device)
            device_props = device_obj.GetProperties(
                dbus_interface='org.chromium.flimflam.Device')
            interfaces.append(str(device_props['Interface']))
        return interfaces


    def run_once(self, devs, nodevs, included, excluded):
        # Stop the normal connman instance, but don't worry if it's not there
        utils.system('initctl stop connman || true')

        # Run connman with our arguments
        # (not using utils.system because we need to background and get the PID)
        # This assumes that 'eth1' is the nonstandard interface
        # path used while testing network stuff.
        argv = ['connmand', '-n', '-W', 'wext','-I', 'eth1']
        for dev in devs:
            argv += ['-i', dev]
        for dev in nodevs:
            argv += ['-I', dev]

        try:
            p = subprocess.Popen(argv)

            # Check up on what connman claims to be managing - wait
            # and loop if it isn't up yet.
            interfaces = None
            while interfaces is None:
                try:
                    interfaces = self.get_interfaces()
                except dbus.DBusException:
                    time.sleep(1)

            not_excluded = [interface for interface in excluded
                            if interface in interfaces]
            wrongly_excluded = [interface for interface in included
                                if interface not in interfaces]
            if not_excluded or wrongly_excluded:
                error_message = ''
                if not_excluded:
                    error_message = (error_message +
                                     'Interfaces not excluded: %s. '
                                     % not_excluded)
                if wrongly_excluded:
                    error_message = (error_message +
                                     'Interfaces wrongly excluded: %s.'
                                     % wrongly_excluded)
                raise error.TestFail(error_message)
        finally:
            # This ensures we don't hang the autotest, which will
            # be waiting on the child connman process.
            p.terminate()
            p.wait()
            # Restart the normal connman instance
            utils.system('initctl start connman')
