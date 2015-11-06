# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from autotest_lib.client.common_lib import error

class PDConsoleUtils(object):
    """ Provides a set of methods common to USB PD FAFT tests

    Each instance of this class is associated with a particular
    servo UART console. USB PD tests will typically use the console
    command 'pd' and its subcommands to control/monitor Type C PD
    connections. The servo object used for UART operations is
    passed in and stored when this object is created.

    """

    SRC_CONNECT = 'SRC_READY'
    SNK_CONNECT = 'SNK_READY'
    SRC_DISC = 'SRC_DISCONNECTED'
    SNK_DISC = 'SNK_DISCONNECTED'

    # dualrole input/ouput values
    DUALROLE_QUERY_DELAY = 0.25
    dual_index = {'on': 0, 'off': 1, 'snk': 2, 'src': 3}
    dualrole_cmd = ['on', 'off', 'sink', 'source']
    dualrole_resp = ['on', 'off', 'force sink', 'force source']

    def __init__(self, console):
        """ Console can be either usbpd, ec, or plankton_ec UART
        This object with then be used by the class which creates
        the PDConsoleUtils class to send/receive commands to UART
        """
        # save console for UART access functions
        self.console = console

    def send_pd_command(self, cmd):
        """Send command to PD console UART

        @param cmd: pd command string
        """
        self.console.send_command(cmd)

    def verify_pd_console(self):
        """Verify that PD commands exist on UART console

        Send 'help' command to UART console
        @returns: True if 'pd' is found, False if not
        """

        l = self.console.send_command_get_output('help', ['(pd)\s+([\w]+)'])
        if l[0][1] == 'pd':
            return True
        else:
            return False

    def execute_pd_state_cmd(self, port):
        """Get PD state for specified channel

        pd 0/1 state command gives produces 5 fields. An example
        is shown here:
        Port C1 CC2, Ena - Role: SRC-DFP-VC State: SRC_READY, Flags: 0x1954

        A dict is created containing port, polarity, role, pd_state, and flags

        @param port: Type C PD port 0 or 1

        @returns: A dict with the 5 fields listed above
        """
        cmd = 'pd'
        subcmd = 'state'
        pd_cmd = cmd +" " + str(port) + " " + subcmd
        pd_state_list = self.console.send_command_get_output(pd_cmd,
                                        ['Port\s+([\w]+)\s+([\w]+)',
                                         'Role:\s+([\w]+-[\w]+)',
                                         'State:\s+([\w]+_[\w]+)',
                                         'Flags:\s+([\w]+)'])

        # Fill the dict fields from the list
        state_result = {}
        state_result['port'] = pd_state_list[0][1]
        state_result['polarity'] = pd_state_list[0][2]
        state_result['role'] = pd_state_list[1][1]
        state_result['pd_state'] = pd_state_list[2][1]
        state_result['flags'] = pd_state_list[3][1]

        return state_result

    def get_pd_state(self, port):
        """Get the current PD state

        @param port: Type C PD port 0/1
        @returns: current pd state
        """

        pd_dict = self.execute_pd_state_cmd(port)
        return pd_dict['pd_state']

    def get_pd_port(self, port):
        """Get the current PD port

        @param port: Type C PD port 0/1
        @returns: current pd state
        """
        pd_dict = self.execute_pd_state_cmd(port)
        return pd_dict['port']

    def get_pd_role(self, port):
        """Get the current PD power role (source or sink)

        @param port: Type C PD port 0/1
        @returns: current pd state
        """
        pd_dict = self.execute_pd_state_cmd(port)
        return pd_dict['role']

    def get_pd_flags(self, port):
        """Get the current PD flags

        @param port: Type C PD port 0/1
        @returns: current pd state
        """
        pd_dict = self.execute_pd_state_cmd(port)
        return pd_dict['flags']

    def get_pd_dualrole(self):
        """Get the current PD dualrole setting

        @returns: current PD dualrole setting
        """
        cmd = 'pd dualrole'
        dual_list = self.console.send_command_get_output(cmd,
                                ['dual-role toggling:\s+([\w ]+)'])
        return dual_list[0][1]

    def set_pd_dualrole(self, value):
        """Set pd dualrole

        It can be set to either:
        1. on
        2. off
        3. snk (force sink mode)
        4. src (force source mode)
        After setting, the current value is read to confirm that it
        was set properly.

        @param value: One of the 4 options listed
        """
        # Get string required for console command
        dual_index = self.dual_index[value]
        # Create console command
        cmd = 'pd dualrole ' + self.dualrole_cmd[dual_index]
        self.console.send_command(cmd)
        time.sleep(self.DUALROLE_QUERY_DELAY)
        # Get current setting to verify that command was successful
        dual = self.get_pd_dualrole()
        # If it doesn't match, then raise error
        if dual != self.dualrole_resp[dual_index]:
            raise error.TestFail("dualrole error: " +
                                 self.dualrole_resp[dual_index] + " != "+dual)

    def query_pd_connection(self):
        """Determine if PD connection is present

        Try the 'pd 0/1 state' command and see if it's in either
        expected state of a conneciton. Record the port number
        that has an active connection

        @returns: dict with params port, connect, and state
        """
        status = {}
        port = 0;
        status['connect'] = False
        status['port'] = port
        state = self.get_pd_state(port)
        # Check port 0 first
        if state == self.SRC_CONNECT or state == self.SNK_CONNECT:
            status['connect'] = True
            status['role'] = state
        else:
            port = 1
            status['port'] = port
            state = self.get_pd_state(port)
            # Check port 1
            if state == self.SRC_CONNECT or state == self.SNK_CONNECT:
                status['connect'] = True
                status['role'] = state

        return status


