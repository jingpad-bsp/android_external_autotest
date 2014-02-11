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
      _servo_prog_state: a tuple of strings of "<control>:<value>" pairs,
                         listing servo controls and their required values for
                         programming
      _servo_saved_state: a list of the same elements as _servo_prog_state,
                          those which need to be restored after programming
      _program_command: a string, the shell command to run on the servo host
                    to actually program the firmware. Dependent on
                    firmware/hardware type, set by subclasses.
    """

    def __init__(self, servo, req_list):
        """Base constructor.
        @param servo: a servo object controlling the servo device
        @param req_list: a list of strings, names of the utilities required
                         to be in the path for the programmer to succeed
        """
        self._servo = servo
        self._servo_prog_state = ()
        self._servo_saved_state = []
        self._program_command = ''
        # These will fail if the utilities are not available, we want the
        # failure happen before run_once() is invoked.
        servo.system('which %s' % ' '.join(req_list))


    def _set_servo_state(self):
        """Set servo for programming, while saving the current state."""
        for item in self._servo_prog_state:
            key, value = item.split(':')
            present = self._servo.get(key)
            if present != value:
                self._servo_saved_state.append('%s:%s' % (key, present))
            self._servo.set(key, value)


    def _restore_servo_state(self):
        """Restore previously saved servo state."""
        self._servo_saved_state.reverse()  # Do it in the reverse order.
        for item in self._servo_saved_state:
            key, value = item.split(':')
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
        super(FlashromProgrammer, self).__init__(servo, ['flashrom',])
        self._servo_prog_state = (
            'spi2_vref:pp3300',
            'spi2_buf_en:on',
            'spi2_buf_on_flex_en:on',
            'spi_hold:off',
            'cold_reset:on',
            )


    def prepare_programmer(self, path, board='unused'):
        """Prepare programmer for programming.

        @param path: a string, name of the file containing the firmware image.
        @param board: unused by this class
        """
        self._program_command = 'flashrom -p ft2232_spi:type=servo-v2 -w %s' % (
            path)


class CrosProgrammer(_BaseProgrammer):
    """Class for programming ARM platform's flashrom through USB."""

    def __init__(self, servo):
        """Configure required servo state."""
        super(CrosProgrammer, self).__init__(
            servo, ['cros_write_firmware', 'dtc', 'smdk-usbdl'])


    def prepare_programmer(self, path, board):
        """Prepare programmer for programming.

        @param path: a string, name of the file containing the firmware image.
        @param board: a string, used to find the appropriate device tree. The
                      device tree is expected to be in the dts subdirectory
                      along with the firmware image file.
        """
        firmware_root = os.path.dirname(path)
        dts_file = os.path.join(
            firmware_root, 'dts',
            'exynos5250-%s.dts' % board)
        self._program_command = 'cros_write_firmware -b daisy -w usb '
        self._program_command += '-d %s -F spi -i %s -V -D' % (dts_file, path)


class OpenocdEcProgrammer(_BaseProgrammer):
    """Class for programming EC firmware using openocd.

    The openocd debugger expects certain scripts/control files to be
    available. The location of the scripts and control files is different for
    cases when the servo device is controlled by local and remote hosts.
    """

    # TODO(vbendeb): clean the paths up once the Beaglebone directory
    # structure/maintenance is formalized. (see http://crosbug.com/35988 for
    # details).
    OPENOCD_SCRIPTS_LOCAL_PATH = os.path.join(os.path.dirname(
            __file__), '..', 'openocd_scripts')
    OPENOCD_SCRIPTS_SERVO_PATH = '/home/chromeos-test/ec/chip/lm4/openocd'
    OPENOCD_CONFIG_SCRIPT = 'servo_v2_slower.cfg'
    OPENOCD_WRITE_COMMAND = """
init; reset halt; flash write_image erase %s 0; reset; shutdown;"""


    def __init__(self, servo):
        """Configure required servo state."""
        super(OpenocdEcProgrammer, self).__init__(servo, ['openocd',])
        self._servo_prog_state = (
            'jtag_buf_on_flex_en:on',
            'jtag_buf_en:on'
            )


    def prepare_programmer(self, path, board='unused'):
        """Prepare programmer for programming.

        @param path: a string, name of the file containing the EC firmware
               image.
        @param board: unused by this class
        """
        if self._servo.is_localhost():
            scripts_path = self.OPENOCD_SCRIPTS_LOCAL_PATH
        else:
            scripts_path = self.OPENOCD_SCRIPTS_SERVO_PATH

        self._program_command = 'openocd -s %s -f %s -c "%s"' % (
            scripts_path, self.OPENOCD_CONFIG_SCRIPT,
            (self.OPENOCD_WRITE_COMMAND % path).strip())


class Stm32monEcProgrammer(_BaseProgrammer):
    """Class for programming EC firmware using stm32mon."""

    def __init__(self, servo):
        """Configure required servo state."""
        super(Stm32monEcProgrammer, self).__init__(servo, ['stm32mon',])
        self._servo_prog_state = (
            'uart1_en:on',
            'uart1_parity:even',
            'uart1_baudrate:115200',
            'spi1_vref:pp3300',
            'cold_reset:on',
            'cold_reset:off'
            )

    def prepare_programmer(self, path, board='unused'):
        """Prepare programmer for programming.

        @param path: a string, name of the file containing the firmware image.
        @param board: unused by this class
        """
        ec_uart_dev = self._servo.get('ec_uart_pty')
        self._program_command = 'stm32mon -d %s -e -w %s' % (ec_uart_dev, path)


def program_ec(board, servo, image):
    """Program EC firmware on the DUT.

    @param board: a string, the DUT board type
    @param servo: a servo object controlling the servo device
    @param image: a string, name of the file containing the new firmware image
    """
    if board in ('link',):
        prog = OpenocdEcProgrammer(servo)
    elif board in ('snow'):
        prog = Stm32monEcProgrammer(servo)
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
    if board in ('link',):
        prog = FlashromProgrammer(servo)
    elif board in ('snow'):
        prog = CrosProgrammer(servo)
    else:
        raise ProgrammerError('unsupported board %s' % board)
    prog.prepare_programmer(image, board)
    prog.program()
