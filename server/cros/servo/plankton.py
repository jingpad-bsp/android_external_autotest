# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re
import time
import xmlrpclib

from autotest_lib.client.bin import utils


class PlanktonError(Exception):
    pass


class Plankton(object):
    """Manages control of a Plankton board via servod XMLRPC.

    Plankton is a testing board developed to aid in USB type C debug and
    control of various type C host devices. Plankton's features include the
    simulation of charger, USB 2.0 pass through, USB 3.0 hub, and display port
    pass through. This class manages setting up and communication with a servo
    daemon (servod) process. It provides high level functions for setting and
    reading USB type C role, mux and common controls.
    """

    DEFAULT_SERVO_HOST = 'localhost'
    DEFAULT_SERVO_PORT = 9999
    # USB charging command delays in seconds.
    USBC_COMMAND_DELAY = 0.5
    # Plankton USBC commands.
    USBC_ROLE = 'usbc_role'
    USBC_MUX = 'usbc_mux'
    RE_USBC_ROLE_VOLTAGE = re.compile(r'src(\d+)v')
    USBC_CHARGING_VOLTAGES = {
        0: 'sink',
        5: 'src5v',
        12: 'src12v',
        20: 'src20v'}
    VBUS_VOLTAGE_MV = 'vbus_voltage'
    VBUS_CURRENT_MA = 'vbus_current'
    VBUS_POWER_MW = 'vbus_power'
    # USBC PD states.
    USBC_PD_STATES = {
        'sink': 'SNK_READY',
        'source': 'SRC_READY'}
    POLL_STATE_SECS = 2


    def __init__(self, args_dict=None):
        """Sets up servo daemon communication.

        @param args_dict: A dictionary contains plankton servod host and port.
                          Example: {'plankton_host': 'localhost',
                                    'plankton_port': 9999}
        """
        if args_dict is None:
            args_dict = {}
        plankton_host = args_dict.get('plankton_host', self.DEFAULT_SERVO_HOST)
        plankton_port = args_dict.get('plankton_port', self.DEFAULT_SERVO_PORT)
        remote = 'http://%s:%s' % (plankton_host, plankton_port)
        self._server = xmlrpclib.ServerProxy(remote)
        self.init_io_expander()


    def init_io_expander(self):
        """Initializes Plankton IO expander register settings."""
        if not int(self.get('debug_usb_sel')):
            raise PlanktonError('debug_usb_sel (SW3) should be ON!! '
                                'Please use CN15 to connect Plankton.')
        self.set('typec_to_hub_sw', '0')
        self.set('usb2_mux_sw', '1')
        self.set('usb_dn_pwren', 'on')


    def set(self, control_name, value):
        """Sets the value of a control using servod."""
        assert control_name
        self._server.set(control_name, value)


    def get(self, control_name):
        """Gets the value of a control from servod."""
        assert control_name
        return self._server.get(control_name)


    @property
    def vbus_voltage(self):
        """Gets Plankton VBUS voltage in volts."""
        return float(self.get(self.VBUS_VOLTAGE_MV)) / 1000.0


    @property
    def vbus_current(self):
        """Gets Plankton VBUS current in amps."""
        return float(self.get(self.VBUS_CURRENT_MA)) / 1000.0


    @property
    def vbus_power(self):
        """Gets Plankton charging power in watts."""
        return float(self.get(self.VBUS_POWER_MW)) / 1000.0


    def get_charging_voltages(self):
        """Gets the lists of available charging voltages."""
        return self.USBC_CHARGING_VOLTAGES.keys()


    def charge(self, voltage):
        """Sets Plankton to provide power at specific voltage.

        @param voltage: Specified charging voltage in volts.
        """
        if voltage not in self.USBC_CHARGING_VOLTAGES:
            raise PlanktonError('Invalid charging voltage: %s' % voltage)

        self.set(self.USBC_ROLE, self.USBC_CHARGING_VOLTAGES[voltage])
        time.sleep(self.USBC_COMMAND_DELAY)


    @property
    def charging_voltage(self):
        """Gets current charging voltage."""
        usbc_role = self.get(self.USBC_ROLE)
        match = self.RE_USBC_ROLE_VOLTAGE(usbc_role)
        if match:
            return int(match.group(1))

        if usbc_role == self.USBC_CHARGING_VOLTAGES[0]:
            return 0

        raise PlanktonError('Invalid USBC role: %s' % usbc_role)


    def poll_pd_state(self, state):
        """Polls until Plankton pd goes to the specific state.

        @param state: Specified pd state name.
        """
        if state not in self.USBC_PD_STATES:
            raise PlanktonError('Invalid state name: %s' % state)
        utils.poll_for_condition(
            lambda: self.get('pd_state') == self.USBC_PD_STATES[state],
            exception=utils.TimeoutError('Plankton not in %s state '
                                         'after %s seconds.' %
                                         (self.USBC_PD_STATES[state],
                                          self.POLL_STATE_SECS)),
            timeout=self.POLL_STATE_SECS)


    def set_usbc_mux(self, mux):
        """Sets Plankton usbc_mux.

        @param mux: Specified mux state name.
        """
        if mux not in ['dp', 'usb']:
            raise PlanktonError('Invalid mux name: %s, '
                                'should be either \'dp\' or \'usb\'.' % mux)
        self.set(self.USBC_MUX, mux)
        time.sleep(self.USBC_COMMAND_DELAY)

