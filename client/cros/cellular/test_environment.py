# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import dbus
import logging
import sys
import traceback

import common
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import backchannel
from autotest_lib.client.cros.cellular import cell_tools
from autotest_lib.client.cros.cellular import mm
from autotest_lib.client.cros.cellular.pseudomodem import pseudomodem_context
from autotest_lib.client.cros.cellular.wardmodem import wardmodem
from autotest_lib.client.cros.networking import cellular_proxy

# Import 'flimflam_test_path' first in order to import flimflam.
# pylint: disable=W0611
from autotest_lib.client.cros import flimflam_test_path
import flimflam

class CellularTestEnvironment(object):
    """Setup and verify cellular test environment.

    This context manager configures the following:
        - Sets up backchannel.
        - Shuts down other devices except cellular.
        - Shill and MM logging is enabled appropriately for cellular.
        - Initializes members that tests should use to access test environment
          (eg. |shill|, |flimflam|, |modem_manager|, |modem|).

    Then it verifies the following is valid:
        - The backchannel is using an Ethernet device.
        - The SIM is inserted and valid.
        - There is one and only one modem in the device.
        - The modem is registered to the network.
        - There is a cellular service in shill and it's not connected.

    Don't use this base class directly, use the appropriate subclass.

    Setup for over-the-air tests:
        with CellularOTATestEnvironment() as test_env:
            # Test body

    Setup for pseudomodem tests:
        with CellularPseudoMMTestEnvironment(
                pseudomm_args=({'family': '3GPP'})) as test_env:
            # Test body

    Setup for wardmodem tests:
        with CellularWardModemTestEnvironment(
                wardmodem_modem='e362') as test_env:
            # Test body

    """

    def __init__(self, use_backchannel=True, shutdown_other_devices=True):
        """
        @param use_backchannel: Set up the backchannel that can be used to
                communicate with the DUT.
        @param shutdown_other_devices: If True, shutdown all devices except
                cellular.

        """
        # Tests should use this main loop instead of creating their own.
        self.mainloop = dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus(mainloop=self.mainloop)

        self.shill = None
        self.flim = None  # Only use this for legacy tests.
        self.modem_manager = None
        self.modem = None

        self._context_managers = []
        if use_backchannel:
            self._context_managers.append(backchannel.Backchannel())
        if shutdown_other_devices:
            self._context_managers.append(
                    cell_tools.OtherDeviceShutdownContext('cellular'))


    def __enter__(self):
        try:
            self._nested = contextlib.nested(*self._context_managers)
            self._nested.__enter__()

            self._initialize_components()
            self._setup_logging()

            self._verify_backchannel()
            self._verify_sim()
            self._wait_for_modem_registration()
            self._verify_cellular_service()

            return self
        except (error.TestError, dbus.DBusException) as e:
            except_type, except_value, except_traceback = sys.exc_info()
            lines = traceback.format_exception(except_type, except_value,
                                               except_traceback)
            logging.error('Error during test initialization:\n' +
                          ''.join(lines))
            self.__exit__(*sys.exc_info())
            raise error.TestError('INIT_ERROR: %s' % str(e))


    def __exit__(self, exception, value, traceback):
        return self._nested.__exit__(exception, value, traceback)


    def _reset_modem(self):
        modem_device = self.shill.find_cellular_device_object()
        if not modem_device:
            raise error.TestError('Cannot find cellular device in shill. '
                                  'Is the modem plugged in?')
        try:
            # Cromo modems do not support being reset.
            self.shill.reset_modem(modem_device, expect_service=False)
        except dbus.DBusException as e:
            if (e.get_dbus_name() !=
                    cellular_proxy.CellularProxy.ERROR_NOT_SUPPORTED):
                raise


    def _initialize_components(self):
        """Get access to various test environment components. """
        # CellularProxy.get_proxy() checks to see if shill is running and
        # responding to DBus requests. It returns None if that's not the case.
        self.shill = cellular_proxy.CellularProxy.get_proxy(self.bus)
        if self.shill is None:
            raise error.TestError('Cannot connect to shill, is shill running?')

        # Keep this around to support older tests that haven't migrated to
        # cellular_proxy.
        self.flim = flimflam.FlimFlam()

        # PickOneModem() makes sure there's a modem manager and that there is
        # one and only one modem.
        self._reset_modem()
        self.modem_manager, modem_path = mm.PickOneModem('')
        self.modem = self.modem_manager.GetModem(modem_path)
        if self.modem is None:
            raise error.TestError('Cannot get modem object at %s.' % modem_path)


    def _setup_logging(self):
        self.shill.set_logging_for_cellular_test()
        self.modem_manager.SetDebugLogging()


    def _verify_backchannel(self):
        """Verify backchannel is on an ethernet device.

        @raise error.TestError if backchannel is not on an ethernet device.

        """
        if not backchannel.is_backchannel_using_ethernet():
            raise error.TestError('An ethernet connection is required between '
                                  'the test server and the device under test.')


    def _verify_sim(self):
        """Verify SIM is valid.

        @raise error.TestError if SIM does not exist or is invalid.

        """
        # TODO: Implement this (crbug.com/403155).
        pass


    def _wait_for_modem_registration(self):
        """Wait for the modem to register with the network.

        The modem should be enabled and registered with the network.

        @raise error.TestError if modem is not registered.

        """
        # TODO: Implement this (crbug.com/403160).
        pass


    def _verify_cellular_service(self):
        """Make sure a cellular service exists.

        The cellular service should not be connected to the network.

        @raise error.TestError if cellular service does not exist or if
                there are multiple cellular services.

        """
        service = self.shill.wait_for_cellular_service_object()

        try:
            service.Disconnect()
        except dbus.DBusException as e:
            if (e.get_dbus_name() !=
                    cellular_proxy.CellularProxy.ERROR_NOT_CONNECTED):
                raise
        success, _, _ = self.shill.wait_for_property_in(
                service,
                cellular_proxy.CellularProxy.SERVICE_PROPERTY_STATE,
                ('idle',),
                cellular_proxy.CellularProxy.SERVICE_DISCONNECT_TIMEOUT)
        if not success:
            raise error.TestError(
                    'Cellular service needs to start in the idle state. '
                    'Modem disconnect may have failed.')


class CellularOTATestEnvironment(CellularTestEnvironment):
    """Setup and verify cellular over-the-air (OTA) test environment. """
    def __init__(self, **kwargs):
        super(CellularOTATestEnvironment, self).__init__(**kwargs)


class CellularPseudoMMTestEnvironment(CellularTestEnvironment):
    """Setup and verify cellular pseudomodem test environment. """
    def __init__(self, pseudomm_args=None, **kwargs):
        """
        @param pseudomm_args: Tuple of arguments passed to the pseudomodem, see
                pseudomodem_context.py for description of each argument in the
                tuple: (flags_map, block_output, bus)

        """
        super(CellularPseudoMMTestEnvironment, self).__init__(**kwargs)
        self._context_managers.append(
                pseudomodem_context.PseudoModemManagerContext(
                        True, bus=self.bus, *pseudomm_args))


class CellularWardModemTestEnvironment(CellularTestEnvironment):
    """Setup and verify cellular ward modem test environment. """
    def __init__(self, wardmodem_modem=None, **kwargs):
        """
        @param wardmodem_modem: Customized ward modem to use instead of the
                default implementation, see wardmodem.py.

        """
        super(CellularWardModemTestEnvironment, self).__init__(**kwargs)
        self._context_managers.append(
                wardmodem.WardModemContext(args=['--modem', wardmodem_modem]))
