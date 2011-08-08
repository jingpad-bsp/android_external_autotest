# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

import dbus, dbus.mainloop.glib, gobject
import glib

from autotest_lib.client.cros import flimflam_test_path
import flimflam, mm

class State:
    ENABLING = 0
    REGISTERING = 1
    CONNECTING = 2
    WAITING = 3
    DISCONNECTING = 4
    DISABLING = 5

class network_3GDormancyDance(test.test):
    version = 1

    def countdown(self):
        self.opsleft -= 1
        print 'Countdown: %d' % (self.opsleft,)
        if self.opsleft == 0:
            self.mainloop.quit()

    def FindModemPath(self):
        for modem in mm.EnumerateDevices():
            (obj, path) = modem
            try:
                if path.index('/org/chromium/ModemManager/Gobi') == 0:
                    return path
            except ValueError:
                pass
        return None

    def RequestDormancyEvents(self, modem_path):
        modem = dbus.Interface(
            self.bus.get_object('org.chromium.ModemManager', modem_path),
            dbus_interface='org.chromium.ModemManager.Modem.Gobi')
        modem.RequestEvents('+dormancy')

    def enable(self):
        print 'Enabling...'
        self.countdown()
        self.state = State.ENABLING
        self.flim.EnableTechnology('cellular')

    def disable(self):
        print 'Disabling...'
        self.countdown()
        self.state = State.DISABLING
        self.flim.DisableTechnology('cellular')

    def connect(self):
        print 'Connecting...'
        self.countdown()
        self.state = State.CONNECTING
        self.flim.ConnectService(service=self.service, config_timeout=120)

    def disconnect(self):
        print 'Disconnecting...'
        self.countdown()
        self.state = State.DISCONNECTING
        self.flim.DisconnectService(service=self.service, wait_timeout=60)

    def PropertyChanged(self, *args, **kwargs):
        if args[0] == 'Powered':
            if not args[1]:
                self.HandleDisabled()
            else:
                self.HandleEnabled()
        elif args[0] == 'Connected':
            if not args[1]:
                self.HandleDisconnected()
            else:
                self.HandleConnected()
        elif args[0] == 'Services':
            self.CheckService()

    def DormancyStatus(self, *args, **kwargs):
        if args[0]:
            self.HandleDormant()

    def FindService(self):
        self.service = self.flim.FindElementByPropertySubstring('Service',
                                                                'Type',
                                                                'cellular')

    def CheckService(self):
        self.FindService()
        if self.state == State.REGISTERING and self.service:
            self.HandleRegistered()

    def HandleDisabled(self):
        if self.state != State.DISABLING:
            raise error.TestFail('Disabled while not in state Disabling')
        print 'Disabled'
        self.enable()

    def HandleEnabled(self):
        if self.state != State.ENABLING:
            raise error.TestFail('Enabled while not in state Enabling')
        print 'Enabled'
        self.state = State.REGISTERING
        print 'Waiting for registration...'
        self.CheckService()

    def HandleRegistered(self):
        if self.state != State.REGISTERING:
            raise error.TestFail('Registered while not in state Registering')
        print 'Registered'
        self.connect()

    def HandleConnected(self):
        if self.state != State.CONNECTING:
            raise error.TestFail('Connected while not in state Connecting')
        print 'Connected'
        self.state = State.WAITING
        print 'Waiting for dormancy...'

    def HandleDormant(self):
        if self.state != State.WAITING:
            raise error.TestFail('Dormant while not in state Waiting')
        print 'Dormant'
        self.disconnect()

    def HandleDisconnected(self):
        if self.state != State.DISCONNECTING:
            raise error.TestFail(
                'Disconnected while not in state Disconnecting')
        print 'Disconnected'
        self.disable()

    def begin(self):
        connected = False
        powered = False

        self.FindService()
        if self.service:
            service_props = self.service.GetProperties(utf8_strings = True)
            if service_props['State'] in ['online', 'portal', 'ready']:
                connected = True
            print 'Service exists, and state is %s.' % (service_props['State'],)
        else:
            print 'Service does not exist.'

        device_props = self.device.GetProperties(utf8_strings = True)
        if device_props['Powered']:
            print 'Device is powered.'
            powered = True
        else:
            print 'Device is unpowered.'

        if powered and connected:
            print 'Starting with Disconnect.'
            self.disconnect()
        elif powered and (not connected):
            print 'Starting with Disable.'
            self.disable()
        elif (not powered) and (not connected):
            print 'Starting with Enable.'
            self.enable()
        else:
            raise error.TestFail('Service online but device unpowered!')

    def run_once(self, name='usb', ops=500, seed=None):
        self.opsleft = ops
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus()

        modem_path = self.FindModemPath()
        if not modem_path:
            raise error.TestFail('No Gobi modem found.')
        print 'Modem: %s' % (modem_path,)
        self.RequestDormancyEvents(modem_path)

        self.flim = flimflam.FlimFlam()
        self.manager = flimflam.DeviceManager(self.flim)
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
