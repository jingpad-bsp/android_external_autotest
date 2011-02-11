# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

import dbus, dbus.mainloop.glib, gobject
import glib

from autotest_lib.client.cros import flimflam_test_path
import flimflam

class network_3GDormancyDance(test.test):
    version = 1

    def countdown(self):
        self.opsleft -= 1
        if self.opsleft == 0:
            self.mainloop.quit()

    def RequestDormancyEvents(self):
        c = self.bus.get_object('org.chromium.ModemManager',
                                '/org/chromium/ModemManager/Gobi/0')
        c.RequestEvents('+dormancy',
                        dbus_interface='org.chromium.ModemManager.Modem.Gobi')

    def enable(self):
        print 'Enable'
        self.countdown()
        self.flim.EnableTechnology('cellular')

    def disable(self):
        print 'Disable'
        self.countdown()
        self.flim.DisableTechnology('cellular')

    def connect(self):
        print 'Connect'
        self.countdown()
        self.flim.ConnectService(service=self.service, config_timeout=120)

    def disconnect(self):
        print 'Disconnect'
        self.countdown()
        self.flim.DisconnectService(service=self.service, wait_timeout=60)

    def PropertyChanged(self, *args, **kwargs):
        print 'PropertyChanged: %s %s' % (args, kwargs)
        if args[0] == 'Powered':
            if not args[1]:
                self.enable()
            else:
                self.connect()
        if args[0] == 'Connected':
            if not args[1]:
                self.disable()


    def DormancyStatus(self, *args, **kwargs):
        print 'DormancyStatus: %s %s' % (args, kwargs)
        if args[0]:
            self.disconnect()

    def begin(self):
        print 'Setup...'
        self.disable()

    def run_once(self, name='usb', ops=5000, seed=None):
        self.opsleft = ops
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus()
        self.RequestDormancyEvents()
        self.flim = flimflam.FlimFlam()
        self.manager = flimflam.DeviceManager(self.flim)
        self.service = self.flim.FindElementByPropertySubstring('Service',
                                                                'Type',
                                                                'cellular')
        self.device = self.flim.FindElementByNameSubstring('Device', name)
        if not self.device:
            self.device = self.flim.FindElementByPropertySubstring('Device',
                                                                   'Interface',
                                                                   name)
        self.bus.add_signal_receiver(self.PropertyChanged,
                                     signal_name='PropertyChanged')
        self.bus.add_signal_receiver(self.DormancyStatus,
                                     signal_name='DormancyStatus')
        self.mainloop = gobject.MainLoop()
        glib.idle_add(self.begin)
        self.mainloop.run()
