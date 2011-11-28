# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus, dbus.mainloop.glib, glib, gobject, logging, time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

from autotest_lib.client.cros import flimflam_test_path
from autotest_lib.client.cros.mainloop import ExceptionForwardingMainLoop
from autotest_lib.client.cros.mainloop import ExceptionForward

import flimflam, mm

class State:
    RESET          = 0
    RESET_GONE     = 1
    RESET_BACK     = 2
    RESET_EVDO     = 3
    ACTIVATE       = 4
    ACTIVATE_GONE  = 5
    ACTIVATE_BACK  = 6
    CONNECT        = 7

class ActivationStateMachine(object):
    """
    Controls the flow of the test.  The expected order of events is:

    1. We factory reset the modem.
    2. The service disappears and returns, and is now not-activated.
    3. We activate the service.
    4. The service cycles again, and is now partially-activated.
    5. The service switches to EVDO and sees a non-zero signal strength.
    6. We connect the service.
    7. The service eventually enters portal state, passing through association,
       configuration, and ready, but no other states.
    8. Start over if we have more loops.
    """

    def __init__(self, tester, loops):
        self.tester = tester
        self.loops_remaining = loops

    def Start(self):
        logging.info('Starting activation test.')
        self.Reset()

    def OnServiceAppeared(self):
        if self.state == State.RESET_GONE:
            logging.info('Service reappeared while resetting.')
            self.state = State.RESET_BACK
        elif self.state == State.ACTIVATE_GONE:
            logging.info('Service reappeared while activating.')
            self.state = State.ACTIVATE_BACK
        else:
            raise error.TestFail('Service appeared unexpectedly')

    def OnServiceDisappeared(self):
        self.is_evdo = False
        self.has_signal = False
        if self.state == State.RESET:
            logging.info('Service disappeared while resetting.')
            self.state = State.RESET_GONE
        elif self.state == State.ACTIVATE:
            logging.info('Service disappeared while activating.')
            self.state = State.ACTIVATE_GONE
        else:
            raise error.TestFail('Service disappeared unexpectedly')

    def OnServiceStateChanged(self, service_state):
        if self.state == State.CONNECT:
            if service_state == 'portal':
                self.Done()
            elif service_state in [ 'association', 'configuration', 'ready' ]:
                logging.info('Service state %s while connecting.' %
                    service_state)
            else:
                raise error.TestFail(
                    'Unexpected service state %s while connecting' %
                    service_state)

    def OnActivationStateChanged(self, activation_state):
        if self.state == State.ACTIVATE_BACK:
            if activation_state == 'partially-activated':
                logging.info('Modem partially-activated.')
                self.Connect()

    def OnNetworkTechnologyChanged(self, technology):
        if self.state == State.RESET_BACK:
            if technology == 'EVDO':
                logging.info('Modem switched to EVDO.')
                self.state = State.RESET_EVDO
        if self.state == State.RESET_EVDO:
            if technology != 'EVDO':
                logging.info('Modem switched from EVDO.')
                self.state = State.RESET_BACK

    def OnStrengthChanged(self, strength):
        if strength <= 0:
            return
        if self.state == State.RESET_EVDO:
            logging.info('Modem has signal strength %d.' % strength)
            self.Activate()

    def Reset(self):
        logging.info('RESET (%d loops left)' % self.loops_remaining)
        self.state = State.RESET
        self.reset_time = time.time()
        self.tester.FactoryReset()

    def Activate(self):
        logging.info('ACTIVATE')
        self.state = State.ACTIVATE
        self.activate_time = time.time()
        self.tester.Activate()

    def Connect(self):
        logging.info('CONNECT')
        self.state = State.CONNECT
        self.connect_time = time.time()
        self.tester.Connect()

    def Done(self):
        self.done_time = time.time()
        self.LogTimes()
        self.loops_remaining -= 1
        if self.loops_remaining > 0:
            self.Reset()
        else:
            self.tester.quit()

    def LogTimes(self):
        reset_time = self.activate_time - self.reset_time
        activate_time = self.connect_time - self.activate_time
        connect_time = self.done_time - self.connect_time

        logging.info('TIMES reset=%.1f activate=%.1f connect=%.1f' %
            (reset_time, activate_time, connect_time))

        self.tester.LogTimes(reset_time, activate_time, connect_time)



class ActivationTester(ExceptionForwardingMainLoop):
    def __init__(self, loops, test, main_loop):
        self.loops = loops
        self.test = test
        super(ActivationTester, self).__init__(
                main_loop,
                timeout_s=120 * loops)

    def CheckModem(self):
        devices = mm.EnumerateDevices()
        if len(devices) == 1:
            (self.manager, self.path) = devices[0]
            self.modem = self.manager.Modem(self.path)
            self.cdma_modem = self.manager.CdmaModem(self.path)
            logging.debug('Modem: %s' % self.path)
            return True
        return False

    def FindModem(self, timeout=5):
        utils.poll_for_condition(
            lambda: self.CheckModem(), timeout=timeout,
            exception=error.TestFail('No modem found (timeout %d)' % timeout))

    def FactoryReset(self):
        self.FindModem()
        self.modem.FactoryReset('000000')

    def Activate(self):
        self.FindModem()
        self.cdma_modem.Activate('')

    def Connect(self):
        self.service.Connect()

    def LogTimes(self, *args):
        self.test.LogTimes(*args)

    def OnServiceStateChanged(self, service_state):
        if service_state == self.service_state:
            return
        logging.debug('Service state changed: %s' % service_state)
        if self.sm:
            self.sm.OnServiceStateChanged(service_state)
        self.service_state = service_state

    def OnActivationStateChanged(self, activation_state):
        if activation_state == self.activation_state:
            return
        logging.debug('Activation state changed: %s' % activation_state)
        if self.sm:
            self.sm.OnActivationStateChanged(activation_state)
        self.activation_state = activation_state

    def OnNetworkTechnologyChanged(self, technology):
        if technology == self.technology:
            return
        logging.debug('Network technology changed: %s' % technology)
        if self.sm:
            self.sm.OnNetworkTechnologyChanged(technology)
        self.technology = technology
        # Sometimes the modem stops sending us signal strength updates when it
        # reconnects.  As a workaround, check the signal strength whenever the
        # network technology changes.
        self.CheckStrength()

    def OnStrengthChanged(self, strength):
        if self.sm:
            self.sm.OnStrengthChanged(strength)

    def CheckStrength(self):
        props = self.service.GetProperties()
        if props.has_key('Strength'):
            self.OnStrengthChanged(props['Strength'])

    @ExceptionForward
    def OnServicePropertyChanged(self, *args, **kwargs):
        property_name = args[0]
        new_value = args[1]
        logging.debug('OnServicePropertyChanged: %s = %r' %
                (property_name, new_value))
        if property_name == 'State':
            self.OnServiceStateChanged(new_value)
        if property_name == 'Cellular.ActivationState':
            self.OnActivationStateChanged(new_value)
        if property_name == 'Cellular.NetworkTechnology':
            self.OnNetworkTechnologyChanged(new_value)
        if property_name == 'Strength':
            self.OnStrengthChanged(new_value)

    def OnServiceAdded(self, service_path):
        if self.service:
            return
        service = self.flimflam.GetObjectInterface('Service', service_path)
        props = service.GetProperties()
        if props['Type'] != 'cellular':
            return
        logging.debug('Service appeared: %s' % service_path)
        self.service_path = service_path
        self.service = service
        match = self.service.connect_to_signal('PropertyChanged',
                                               self.OnServicePropertyChanged)
        self.svc_prop_match = match
        # Make sure we are seeing fresh properties -- we don't want a property
        # to be set after we get the props above but before we add the handler.
        props = service.GetProperties()
        if self.sm:
            self.sm.OnServiceAppeared()
        if 'State' in props:
            self.OnServiceStateChanged(props['State'])
        if 'Cellular.ActivationState' in props:
            self.OnActivationStateChanged(props['Cellular.ActivationState'])
        if 'Cellular.NetworkTechnology' in props:
            self.OnNetworkTechnologyChanged(props['Cellular.NetworkTechnology'])

    def OnServiceRemoved(self, service_path):
        if service_path == self.service_path:
            logging.debug('Service disappeared: %s' % service_path)
            self.service_path = None
            self.service = None
            if self.sm:
                self.sm.OnServiceDisappeared()
            self.svc_prop_match.remove()
            self.svc_prop_match = None

    @ExceptionForward
    def OnServicesChanged(self, new_services):
        for service in self.old_services:
            if service not in new_services:
                self.OnServiceRemoved(service)
        for service in new_services:
            if service not in self.old_services:
                self.OnServiceAdded(service)
        self.old_services = new_services

    @ExceptionForward
    def OnManagerPropertyChanged(self, *args, **kwargs):
        property_name = args[0]
        new_value = args[1]
        logging.debug('OnManagerPropertyChanged: %s = %r' %
                (property_name, new_value))
        if property_name == 'Services':
            self.OnServicesChanged(new_value)

    @ExceptionForward
    def idle(self):
        self.sm = None

        self.flimflam = flimflam.FlimFlam()

        self.service = None
        self.service_path = None
        self.old_services = []
        self.svc_prop_match = None

        self.service_state = None
        self.activation_state = None
        self.technology = None

        bus = dbus.SystemBus()
        self.flimflam.manager.connect_to_signal('PropertyChanged',
                                                self.OnManagerPropertyChanged)

        mgr_props = self.flimflam.manager.GetProperties()
        self.OnServicesChanged(mgr_props['Services'])

        self.sm = ActivationStateMachine(tester=self, loops=self.loops)
        self.sm.Start()


def average(list):
    return sum(list) / len(list)


class network_3GActivateCdma(test.test):
    version = 1

    def run_once(self, loops=3):
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        main_loop = gobject.MainLoop()

        self.reset_times = []
        self.activate_times = []
        self.connect_times = []

        ActivationTester(loops=loops, test=self, main_loop=main_loop).run()

        self.CalculateStats()

    def LogTimes(self, reset_time, activate_time, connect_time):
        self.reset_times.append(reset_time)
        self.activate_times.append(activate_time)
        self.connect_times.append(connect_time)

    def CalculateStats(self):
        self.write_perf_keyval({
            'reset_time_average': average(self.reset_times),
            'activate_time_average': average(self.activate_times),
            'connect_time_average': average(self.connect_times)})
