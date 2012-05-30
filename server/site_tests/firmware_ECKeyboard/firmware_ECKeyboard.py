# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from autotest_lib.server.cros.faftsequence import FAFTSequence


# en-US key matrix (from "kb membrane pin matrix.pdf")
KEYMATRIX = {'`': (3, 1), '1': (6, 1), '2': (6, 4), '3': (6, 2), '4': (6, 3),
             '5': (3, 3), '6': (3, 6), '7': (6, 6), '8': (6, 5), '9': (6, 9),
             '0': (6, 8), '-': (3, 8), '=': (0, 8), 'q': (7, 1), 'w': (7, 4),
             'e': (7, 2), 'r': (7, 3), 't': (2, 3), 'y': (2, 6), 'u': (7, 6),
             'i': (7, 5), 'o': (7, 9), 'p': (7, 8), '[': (2, 8), ']': (2, 5),
             '\\': (3, 11), 'a': (4, 1), 's': (4, 4), 'd': (4, 2), 'f': (4, 3),
             'g': (1, 3), 'h': (1, 6), 'j': (4, 6), 'k': (4, 5), 'l': (4, 9),
             ';': (4, 8), '\'': (1, 8), 'z': (5, 1), 'x': (5, 4), 'c': (5, 2),
             'v': (5, 3), 'b': (0, 3), 'n': (0, 6), 'm': (5, 6), ',': (5, 5),
             '.': (5, 9), '/': (5, 8), ' ': (5, 11), '<right>': (6, 12),
             '<alt_r>': (0, 10), '<down>': (6, 11), '<tab>': (2, 1),
             '<f10>': (0, 4), '<shift_r>': (7, 7), '<ctrl_r>': (4, 0),
             '<esc>': (1, 1), '<backspace>': (1, 11), '<f2>': (3, 2),
             '<alt_l>': (6, 10), '<ctrl_l>': (2, 0), '<f1>': (0, 2),
             '<search>': (0, 1), '<f3>': (2, 2), '<f4>': (1, 2), '<f5>': (3, 4),
             '<f6>': (2, 4), '<f7>': (1, 4), '<f8>': (2, 9), '<f9>': (1, 9),
             '<up>': (7, 11), '<shift_l>': (5, 7), '<enter>': (4, 11),
             '<left>': (7, 12)}


class firmware_ECKeyboard(FAFTSequence):
    """
    Servo based EC keyboard test.
    """
    version = 1


    # Delay for remote shell command call to return
    RPC_DELAY = 0.5

    # Delay between commands
    CMD_DELAY = 1


    def key_down(self, keyname):
        self.faft_client.run_shell_command('ectool kbpress %d %d 1' %
                (KEYMATRIX[keyname][0], KEYMATRIX[keyname][1]))


    def key_up(self, keyname):
        self.faft_client.run_shell_command('ectool kbpress %d %d 0' %
                (KEYMATRIX[keyname][0], KEYMATRIX[keyname][1]))


    def delayed_key_press(self, keyname):
        r, c = KEYMATRIX[keyname]
        cmd = '(sleep %d; ectool kbpress %d %d 1; ectool kbpress %d %d 0;)&'
        self.faft_client.run_shell_command(cmd % (self.RPC_DELAY, r, c, r, c))


    def key_press(self, keyname):
        self.key_down(keyname)
        self.key_up(keyname)


    def send_string(self, string):
        for c in string:
            self.key_press(c)

    def switch_tty2(self):
        """Switch to tty2 console."""
        self.key_down('<ctrl_l>')
        self.key_down('<alt_l>')
        self.key_down('<f2>')
        self.key_up('<f2>')
        self.key_up('<alt_l>')
        self.key_up('<ctrl_l>')
        time.sleep(self.CMD_DELAY)


    def reboot_by_keyboard(self):
        """
        Simulate key press sequence to log into console and then issue reboot
        command.
        """
        self.switch_tty2()
        self.send_string('root')
        self.key_press('<enter>')
        time.sleep(self.CMD_DELAY)
        self.send_string('test0000')
        self.key_press('<enter>')
        time.sleep(self.CMD_DELAY)
        self.send_string('reboot')
        self.delayed_key_press('<enter>')


    def run_once(self, host=None):
        self.register_faft_sequence((
            {   # Step 1, use key press simulation to issue reboot command
                'reboot_action': self.reboot_by_keyboard,
            },
            {   # Step 2, reboot EC to ensure releasing all simulated key
                'reboot_action': self.sync_and_ec_reboot,
            },
            {   # Step 3, dummy step to ensure reboot
            }
        ))
        self.run_faft_sequence()
