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
    # Set default logging level to INFO
    logger.setLevel(logging.INFO)
    # Create file handler and set level to DEBUG
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)
    # Create console handler and set level to INFO
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    # Create formatter
    formatter = logging.Formatter('%(asctime)s [%(levelname)s]: %(message)s')
    # Add formatter to handlers
    fh.setFormatter(formatter)
    #ch.setFormatter(formatter)
    # Add handlers to logger
    logger.addHandler(fh)
    logger.addHandler(ch)


def get_gpio_data(gpio_pin, filename, use_pin_offset=True):
    """
    Gets GPIO pin offset and desired data file path.

    @param gpio_pin: a GpioPin tuple, defined in constants.py.
    @param filename: a string, data file name.
    @param use_pin_offset: a boolean, True == use pin offset in gpio_file path.
    @returns pin_offset: a string, pin offset.
    @returns gpio_file: a string, file path of GPIO pin data.
    """
    pin_offset = str(gpio_pin.bank * c.GPIO_BANK_LEN + gpio_pin.bit)
    path_components = [c.SYS_GPIO_PATH]
    if use_pin_offset:
        path_components.append(c.GPIO + pin_offset)
    path_components.append(filename)
    return pin_offset, os.sep.join(path_components)
