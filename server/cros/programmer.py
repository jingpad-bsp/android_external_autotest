# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A utility to program Chrome OS devices' firmware using servo.

This utility expects the DUT to be connected to a servo device. This allows us
to put the DUT into the required state and to actually program the DUT's
firmware using FTDI, USB and/or serial interfaces provided by servo.

Servo state is preserved across the programming process.
"""

import os

class ProgrammerError(Exception):
    """Local exception class wrapper."""
    pass


class _BaseProgrammer(object):
    """Class implementing base programmer services.

    Private attributes:
      _servo: a servo object controlling the servo device
      _servo_prog_state: a dictionary, where keys are servo attributes and
                    values are required state of these attributes during
                    programming process. Dependent on firmware/hardware type,
                    set by subclasses.
      _servo_saved_state: a dictionary, where keys are servo attributes and
                    values are their state before programming process started.
                    Used to restore servo state after programming.
      _program_command: a string, the shell command to run on the servo host
                    to actually program the firmware. Dependent on
                    firmware/hardware type, set by subclasses.
    """

    def __init__(self, servo):
        """Base constructor.
        @param servo: a servo object controlling the servo device
        """
        self._servo = servo
        self._servo_prog_state = {}
        self._servo_saved_state = {}
        self._program_command = ''
        # These will fail if the utilities are not available, we want the
        # failure happen before run_once() is invoked.
        servo.system('which openocd')
        servo.system('which flashrom')


    def _set_servo_state(self):
        """Set servo for programming, while saving the current state."""
        for key, value in self._servo_prog_state.iteritems():
            self._servo_saved_state[key] = self._servo.get(key)
            self._servo.set(key, value)


    def _restore_servo_state(self):
        """Restore previously saved servo state."""
        for key, value in self._servo_saved_state.iteritems():
            self._servo.set(key, value)


    def program(self):
        """Program the firmware as configured by a subclass."""
        self._set_servo_state()
        try:
            self._servo.system(self._program_command)
        finally:
            self._restore_servo_state()


class FlashromProgrammer(_BaseProgrammer):
    """Class for programming AP flashrom."""

    def __init__(self, servo):
        """Configure required servo state."""
        super(FlashromProgrammer, self).__init__(servo)
        self._servo_prog_state = {
            'spi2_vref': 'pp3300',
            'spi2_buf_en': 'on',
            'spi2_buf_on_flex_en': 'on',
            'spi_hold': 'off',
            'cold_reset': 'on'
            }


    def prepare_programmer(self, path):
        """Prepare programmer for programming.

        If necessary - copy the image to the servo host. Define the shell
        command to use to program.

        @param path: a string, name of the file containing the firmware image.
        """
        self._program_command = 'flashrom -p ft2232_spi:type=servo-v2 -w %s' % (
            path)


class LinkEcProgrammer(_BaseProgrammer):
    """Class for programming Link EC firmware.

    Programming Link EC requires openocd debugger, which in turn expects
    certain scripts/control files to be available. The location of the scripts
    and control files is different for cases when the servo device is
    controlled by local and remote hosts.
    """

    # TODO(vbendeb): clean the paths up once the Beaglebone directory
    # structure/maintenance is formalized. (see http://crosbug.com/35988 for
    # details).
    OPENOCD_SCRIPTS_LOCAL_PATH = os.path.join(os.path.dirname(
            __file__), 'openocd_scripts')
    OPENOCD_SCRIPTS_SERVO_PATH = '/home/chromeos-test/ec/chip/lm4/openocd'
    OPENOCD_CONFIG_SCRIPT = 'servo_v2_slower.cfg'
    OPENOCD_WRITE_COMMAND = """
init; reset halt; flash write_image erase %s 0; reset; shutdown;"""


    def __init__(self, servo):
        """Configure required servo state."""
        super(LinkEcProgrammer, self).__init__(servo)
        self._servo_prog_state = {
            'jtag_buf_on_flex_en': 'on',
            'jtag_buf_en': 'on'
            }


    def prepare_programmer(self, path):
        """Prepare programmer for programming.

        If necessary - copy the image to the servo host. Define the shell
        command to use to program.

        @param path: a string, name of the file containing the EC firmware
               image.
        """
        if self._servo.is_localhost():
            scripts_path = self.OPENOCD_SCRIPTS_LOCAL_PATH
        else:
            scripts_path = self.OPENOCD_SCRIPTS_SERVO_PATH

        self._program_command = 'openocd -s %s -f %s -c "%s"' % (
            scripts_path, self.OPENOCD_CONFIG_SCRIPT,
            (self.OPENOCD_WRITE_COMMAND % path).strip())


def program_ec(board, servo, image):
    """Program EC firmware on the DUT.

    @param board: a string, the DUT board type
    @param servo: a servo object controlling the servo device
    @param image: a string, name of the file containing the new firmware image
    """
    if board in ('link',):
        prog = LinkEcProgrammer(servo)
    else:
        raise ProgrammerError('unsupported board %s' % board)

    prog.prepare_programmer(image)
    prog.program()


def program_bootprom(board, servo, image):
    """Program AP firmware on the DUT.

    @param board: a string, the DUT board type (not yet used)
    @param servo: a servo object controlling the servo device
    @param image: a string, name of the file containing the new firmware image
    """
    prog = FlashromProgrammer(servo)
    prog.prepare_programmer(image)
    prog.program()
