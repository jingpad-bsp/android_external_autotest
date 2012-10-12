# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ast

from autotest_lib.client.common_lib import error

class ChromeEC(object):
    """Manages control of a Chrome EC.

    We control the Chrome EC via the UART of a Servo board. Chrome EC
    provides many interfaces to set and get its behavior via console commands.
    This class is to abstract these interfaces.
    """

    def __init__(self, servo):
        """Initialize and keep the servo object.

        Args:
          servo: A Servo object.
        """
        self._servo = servo


    def send_command(self, command):
        """Send command through UART.

        This function opens UART pty when called, and then command is sent
        through UART.

        Args:
          command: The command string to send.
        """
        self._servo.set('ec_uart_regexp', 'None')
        self._servo.set_nocheck('ec_uart_cmd', command)


    def send_command_get_output(self, command, regexp_list, timeout=1):
        """Send command through UART and wait for response.

        This function waits for response message matching regular expressions.

        Args:
          command: The command sent.
          regexp_list: List of regular expressions used to match response
            message. Note, list must be ordered.

        Returns:
          List of tuples, each of which contains the entire matched string and
          all the subgroups of the match. None if not matched.
          For example:
            response of the given command:
              High temp: 37.2
              Low temp: 36.4
            regexp_list:
              ['High temp: (\d+)\.(\d+)', 'Low temp: (\d+)\.(\d+)']
            returns:
              [('High temp: 37.2', '37', '2'), ('Low temp: 36.4', '36', '4')]

        Raises:
          error.TestError: An error when the given regexp_list is not valid.
        """
        if not isinstance(regexp_list, list):
            raise error.TestError('Arugment regexp_list is not a list: %s' %
                                  str(regexp_list))

        self._servo.set('ec_uart_timeout', str(float(timeout)))
        self._servo.set('ec_uart_regexp', str(regexp_list))
        self._servo.set_nocheck('ec_uart_cmd', command)
        return ast.literal_eval(self._servo.get('ec_uart_cmd'))
