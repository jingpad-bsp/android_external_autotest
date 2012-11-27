# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Utility methods used in this module.
"""

import logging
import os

import constants as c


def config_logger(logger, log_file):
    """
    Sets up logger to output to both stdout and a file.

    Code modified from:
    http://docs.python.org/2/howto/logging-cookbook.html#logging-cookbook

    @param logger: a logger object.
    @param log_file: a string, name of log file.
    """
    # Set logging level
    logger.setLevel(logging.DEBUG)
    # Create file handler and set level to debug
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)
    # Create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    # Create formatter
    formatter = logging.Formatter('%(asctime)s [%(levelname)s]: %(message)s')
    # Add formatter to handlers
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    # Add handlers to logger
    logger.addHandler(fh)
    logger.addHandler(ch)


def get_gpio_data(gpio_pin, filename):
    """
    Gets GPIO pin offset and desired data file path.

    Example: get_gpio_data(1, 2, 'value') returns
        pin_offset '34' (1 * 32 + 2 = 34) and
        gpio_file '/sys/class/gpio/gpio34/value'

    @param gpio_pin: a GpioPin tuple, defined in constants.py.
    @param filename: a string, data file name.
    @returns pin_offset: a string, pin offset.
    @returns gpio_file: a string, file path of GPIO pin data.
    """
    pin_offset = str(gpio_pin.bank * c.GPIO_BANK_LEN + gpio_pin.bit)
    gpio_file = os.path.join(
        c.SYS_GPIO_PATH, c.GPIO + pin_offset, filename)
    return pin_offset, gpio_file
