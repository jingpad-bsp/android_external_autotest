# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Simple script to set attenuation level on a variable attenuator.

Pre-requisite:
    Run attenuator_init.py to initialize BeagleBone first.

Sample usage:
    python attenuator_config.py -p 1 -f 35 -t 60
    (set attenuator at port #1 to 60dB, with 35dB fixed path loss)

    python attenuator_config.py -p 0
    (read attenuation value from attenuator at port #0)
"""

import argparse
import copy
import errno
import logging

import attenuator_util
import constants as c


class Attenuator(object):
  """Controller for a variable attenuator."""

  def __init__(self, port, logger):
      """
      @param port: an integer, port of variable attenuator.
      @param logger: a logger object, ready for use.
      """
      self.port = port
      self.logger = logger

  def _get_bit_value(self, gpio_pin):
      """
      Gets bit value of a specific GPIO pin.

      Bit value (0 or 1) for GPIO pin N is stored in a one-line file
          /sys/class/gpio/gpioN/value

      @param gpio_pin: a GpioPin tuple, defined in constants.py.
      @return an integer, bit value (0 or 1). Or None.
      @raises AttenuatorError: if error reading pin value.
      """
      pin_offset, gpio_file = attenuator_util.get_gpio_data(gpio_pin,
                                                            c.VALUE_FILE)
      try:
          with open(gpio_file, 'r') as f:
              bit_value = f.readline()
              return int(bit_value[0], 2)
      except IOError as e:
          if e.errno == errno.ENOENT:
              raise c.AttenuatorError('GPIO pin %s not found. Please run '
                                      'attenuator_init.py first.' % pin_offset)
      return None


  def get_attenuation(self):
      """
      Reads attenuation value (in dB) from GPIO value files of an attenuator.

      Attenuation values are stored as 7-bit integers in 1 dB increment.

      @return db_value: an integer, attenuation in dB.
      @raises AttenuatorError: if error reading pin value.
      """
      db_value = None
      self.logger.info('Getting attenuation value for attenuator %d', self.port)
      descending_pins = copy.deepcopy(c.PINS_FOR_PORT[self.port])
      descending_pins.reverse()  # reverse bits to be in descending order
      for index, pin in enumerate(descending_pins):
          pin_value = self._get_bit_value(pin)
          self.logger.debug('bank %d, bit %d has value %s',
                            pin.bank, pin.bit, pin_value)
          if pin_value is None:
              err = ('Error reading pin value (bank %d, bit %d)' %
                     (pin.bank, pin.bit))
              raise c.AttenuatorError(err)

          if db_value is None:
              db_value = pin_value
          else:
              db_value |= pin_value
          # Left shift by 1 bit before reaching end of the array
          if index < (len(descending_pins) - 1):
              db_value <<= 1

      self.logger.info('db_value = %d (0x%x)', db_value, db_value)
      if db_value < 0 or db_value > c.MAX_VARIABLE_ATTENUATION:
          raise c.AttenuatorError('Invalid attenuation value: %s' % db_value)
      return db_value


  def _set_bit_value(self, gpio_pin, bit_value):
      """
      Sets bit value of a specific GPIO pin.

      @param gpio_pin: a GpioPin tuple, defined in constants.py.
      @param bit_value: an integer, 0 or 1.
      @raises AttenuatorError: if error setting pin value.
      """
      assert str(bit_value) in c.VALID_BIT_VALUE
      pin_offset, gpio_file = attenuator_util.get_gpio_data(gpio_pin,
                                                            c.VALUE_FILE)
      try:
          with open(gpio_file, 'w') as f:
              f.write(str(bit_value))
              self.logger.debug('Wrote bit value %d to pin %s',
                                bit_value, pin_offset)
      except IOError as e:
          if e.errno == errno.ENOENT:
              raise c.AttenuatorError('GPIO pin %s not found. Please run '
                                      'attenuator_init.py first.' % pin_offset)


  def set_attenuation(self, db_value):
      """
      Sets attenuation value (in dB) on an attenuator.

      Attenuation levels are stored in denominations of 1 dB.

      @param db_value: an integer, attenuation value in dB.
      """
      self.logger.info('Setting attenuator %d to %d dB', self.port, db_value)
      for pin in c.PINS_FOR_PORT[self.port]:
          self.logger.debug('Setting bit value for bank %d, bit %d',
                            pin.bank, pin.bit)
          self._set_bit_value(pin, db_value & 1)
          db_value >>= 1


def run(args):
    """
    @param args: a dict, command-line args.
    @raises AttenuatorError: if error setting attenuation.
    """
    logger = logging.getLogger('attenuator_config')
    attenuator_util.config_logger(logger, 'attenuator_config.log')
    logger.info('args = %r', args)

    controller = Attenuator(args.port, logger)
    if args.total_loss is None:
        # Read current attenuation value
        variable_loss = controller.get_attenuation()
        total_loss = variable_loss + args.fixed_loss
        logger.info('Attenuator %d has total loss of %d dB',
                    args.port, total_loss)
        return

    # Sanity check fixed loss in relation to total loss
    if args.fixed_loss > args.total_loss:
        err = ('fixed loss %d should not be greater than total loss %d' %
               (args.fixed_loss, args.total_loss))
        raise c.AttenuatorError(err)

    variable_loss = args.total_loss - args.fixed_loss
    if variable_loss > c.MAX_VARIABLE_ATTENUATION:
        err = (('total loss (%d) - fixed loss (%d) results in variable loss'
                ' (%d) exceeding maximum available value (%d)') %
               (args.total_loss, args.fixed_loss, variable_loss,
                c.MAX_VARIABLE_ATTENUATION))
        raise c.AttenuatorError(err)

    # Set attenuation value
    logger.info('Attenuator %d: set attenuation to %d dB',
                args.port, variable_loss)
    controller.set_attenuation(variable_loss)
    # Read back to verify
    readback = controller.get_attenuation()
    if readback != variable_loss:
        err = 'read back %d, expected %d' % (readback, variable_loss)
        raise c.AttenuatorError(err)


def main():
    """Program entry point."""

    parser = argparse.ArgumentParser(
        description='BeagleBone attenuator params')
    # BeagleBone supports up to 4 variable attenuators.
    parser.add_argument(
        '-p', '--port', type=int, choices=c.VALID_PORTS,
        help='0-based port of variable attenuator')
    parser.add_argument(
        '-f', '--fixed_loss', type=int, help='fixed path loss in dB')
    parser.add_argument(
        '-t', '--total_loss', type=int,
        help='Desired total attenuation in dB (including fixed path loss)')

    run(parser.parse_args())


if __name__ == '__main__':
  main()
