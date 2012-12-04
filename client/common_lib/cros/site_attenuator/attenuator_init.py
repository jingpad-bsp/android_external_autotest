# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Simple script to initialize pin muxing to GPIO modes.

@see BeagleBone System Reference Manual (RevA3_1.0):
    http://beagleboard.org/static/beaglebone/a3/Docs/Hardware/BONE_SRM.pdf
@see Texas Instrument's GPIO Driver Guide
    http://processors.wiki.ti.com/index.php/GPIO_Driver_Guide

Sample usage:
    python attenuator_init.py -p 0
    (initializes attenuator at port 0)

    python attenuator_init.py -p 0 -c
    (unexport GPIO pins of attenuator at port 0)
"""

import argparse
import errno
import logging
import os

import attenuator_util
import constants as c


class InitAttenuator(object):
    """
    Initializes attenuator for GPIO operations.
    """

    def __init__(self, port, logger):
        """
        @param port: an integer, 0-based port index.
        @param logger: a logger object, ready for use.
        """
        self.port = port
        self.logger = logger


    def _set_gpio_mode(self, pin_name):
        """
        Sets pin_name to GPIO mode (0x7).

        @param pin_name: a string, master pin name.
        """
        sysfile = os.path.join(c.PINMUX_PATH, pin_name)
        with open(sysfile, 'wb') as f:
            f.write(c.CONF_GPIO_MODE)


    def setup_gpio_modes(self):
        """
        Sets relevant pins to GPIO mode.

        @raises AttenuatorError: if error setting pin mode to GPIO.
        """
        for pin in c.PINS_FOR_PORT[self.port]:
            self.logger.info('Setting pin (%s) to GPIO mode', pin.pinmux_file)
            self._set_gpio_mode(pin.pinmux_file)
            pin_modes = self.get_pin_muxing_modes(pin.pinmux_file)
            if c.OMAP_MUX_GPIO_MODE not in pin_modes:
                err = 'Error setting pin %s to GPIO mode' % pin.pinmux_file
                raise c.AttenuatorError(err)


    def get_pin_muxing_modes(self, pin_name):
        """
        Reads pin muxing value.

        Sample pin muxing file content (for one pin):
          $ cat /sys/kernel/debug/omap_mux/gpmc_ad0
          name: gpmc_ad0.(null) (0x44e10800/0x800 = 0x0007), b NA, t NA
          mode: OMAP_PIN_OUTPUT | OMAP_MUX_MODE7
          signals: gpmc_ad0 | mmc1_dat0 | NA | NA | NA | NA | NA | NA

        Pin muxing mode is described by 'mode: ...' line.

        @param pin_name: a string, master pin name.
        @return a list of strings, pin modes. Or None.
        """
        modes = None
        sysfile = os.path.join(c.PINMUX_PATH, pin_name)
        self.logger.info('reading content of %s', sysfile)
        with open(sysfile, 'r') as f:
            for line in f:
                if line.startswith('mode:'):
                    modes = [i.strip() for i in line[5:].split('|')]
        self.logger.debug('modes = %r', modes)
        return modes


    def _enable_gpio_pin(self, gpio_pin):
        """
        Exports specified GPIO pin and set its mode to output.

        Example steps enable GPIO pin 62 for 'output' mode (on Angstrom Linux)
        1. Write string '62' to file '/sys/class/gpio/export'. This creates
           a new directory '/sys/class/gpio/gpio62' with a few config files.
        2. Set pin mode to 'output' by writing string 'out' to
           '/sys/class/gpio/gpio62/direction'

        @param gpio_pin: a GpioPin tuple, defined in constants.py.
        """
        pin_offset, export_file = attenuator_util.get_gpio_data(
            gpio_pin, c.EXPORT_FILE, use_pin_offset=False)

        # Open up the pin
        try:
            with open(export_file, 'w') as f:
                f.write(pin_offset)
        except IOError as e:
            if e.errno == errno.EBUSY:
                self.logger.warning('GPIO pin %s already enabled', pin_offset)
            else:
                raise e  # Re-raise
        else:
            self.logger.info('GPIO pin %s enabled', pin_offset)

        # Set it to output
        gpio_file = os.path.join(
            c.SYS_GPIO_PATH, c.GPIO + pin_offset, c.DIRECTION_FILE)
        with open(gpio_file, 'w') as f:
            f.write(c.MODE_OUT)
        self.logger.info('GPIO pin %s set to output', pin_offset)


    def _disable_gpio_pin(self, gpio_pin):
        """
        Unexports specified GPIO pin.

        @param gpio_pin: a GpioPin tuple, defined in constants.py.
        """
        pin_offset, unexport_file = attenuator_util.get_gpio_data(
            gpio_pin, c.UNEXPORT_FILE, use_pin_offset=False)
        try:
            with open(unexport_file, 'w') as f:
                f.write(pin_offset)
        except IOError as e:
            if e.errno == errno.EINVAL:
                self.logger.warning('GPIO pin %s already disabled', pin_offset)


    def setup_gpio_files(self, cleanup=False):
        """
        Creates or removes sysfs entries for all pins required by an attenuator.

        Upon a new boot, create GPIO output pins.

        @param cleanup: a boolean, True to unexport GPIO pins.
        @raises AttenuatorError: if error creating sysfs entry.
        """
        for pin in c.PINS_FOR_PORT[self.port]:
            if cleanup:
                self.logger.info('Disable GPIO pin (bank %d, pin %d)',
                                 pin.bank, pin.bit)
                self._disable_gpio_pin(pin)
            else:
                self.logger.info('Enable GPIO pin (bank %d, pin %d)',
                                 pin.bank, pin.bit)
                self._enable_gpio_pin(pin)


def main():
  parser = argparse.ArgumentParser(
      description='Variable attenuator params')
  # BeagleBone supports up to 4 variable attenuators.
  parser.add_argument(
      '-p', '--port', nargs='?', type=int, default=0, choices=c.VALID_PORTS,
      help='0-based port of variable attenuator')
  parser.add_argument(
      '-c', '--cleanup', action='store_true', help='unexport GPIO pins')
  args = parser.parse_args()

  mylog = logging.getLogger('attenuator_init')
  attenuator_util.config_logger(mylog, 'attenuator_init.log')
  initializer = InitAttenuator(args.port, mylog)
  initializer.setup_gpio_modes()
  initializer.setup_gpio_files(args.cleanup)


if __name__ == '__main__':
  main()
