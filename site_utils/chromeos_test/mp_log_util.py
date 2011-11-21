#!/usr/bin/python
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Helper class for setting up the logging with mp_thread_pool."""

__author__ = 'pauldean@google.com (Paul Pendlebury)'

import logging.handlers
import optparse
import os

# Max size to grow log files, in bytes.
MAX_FILE_SIZE = 1024000

# Number of backups RotatingFileHandler should keep.
BACKUP_FILE_COUNT = 10


def InitializeLogging(logger=None, log_file=None, skip_console=False,
                      verbose=False, **kwargs):
  """Configure a logger instance.

  Args:
    logger: logger instance to setup, if non configures global logger.
    log_file: log file name.
    skip_console: if true do not write log message to console.
    verbose: set logger level to DEBUG.
    kwargs: ignored extra args.
  """
  if logger is None:
    logger = logging.getLogger()

  fmt = '%(levelname)s: %(message)s'
  dbg_fmt = ''
  log_level = logging.INFO
  if verbose:
    # For debug level logging add process and thread info to messages.
    dbg_fmt = '%(process)d:%(threadName)s '
    log_level = logging.DEBUG

  if log_file:
    # Setup file logging.  Parent PID is useful in log files when messages
    # overlap from different instances of a script.  So add it to the log
    # messages.
    log_fmt = '%(asctime)s ' + repr(os.getppid()) + ': '
    hf = logging.Formatter(log_fmt + dbg_fmt + fmt)
    h = logging.handlers.RotatingFileHandler(filename=log_file,
                                             maxBytes=MAX_FILE_SIZE,
                                             backupCount=BACKUP_FILE_COUNT)
    h.setFormatter(hf)
    logger.addHandler(h)

  # Setup console logging.
  if not skip_console:
    log_fmt = '%(asctime)s '
    cf = logging.Formatter(log_fmt + dbg_fmt + fmt, '%H:%M:%S')
    c = logging.StreamHandler()
    c.setFormatter(cf)
    logger.addHandler(c)

  logger.setLevel(log_level)


def LogWithHeader(message, logger=None, width=60, symbol='='):
  """Display a message surrounded by solid lines to make it stand out.

  Print a leading and trailing line of width=count of character=symbol.
  Print a centered string=message, and if there is space insert symbol into
  front and end of string.

  PrettyPrintHeader('Run Start: Graph HTML', 50) would display:
  =================================================
  ============= Run Start: Graph HTML =============
  =================================================

  If message is longer than width, it is printed as is between lines of symbol.

  If message is shorter than width but contains newline characters the output
  will not be padded with symbols on the left/right.

  Args:
    message: text string to print.
    logger: logger to use
    width: number of characters per line.
    symbol: character to print as decoration.
  """
  if logger is None:
    logger = logging.getLogger()

  msg = message
  msg_header = width * symbol

  # +2 for space on either side of message.
  if width > len(message) + 2 and not message.count('\n'):
    spaced_msg = ' %s ' % message
    fill_space = width - len(spaced_msg)
    if fill_space % 2 != 0: spaced_msg += ' '  # Put uneven space on right.
    fill_space /=  2
    symbol_fill = symbol * fill_space
    msg = symbol_fill + spaced_msg + symbol_fill

  log_msg = '\n'.join(['',  # empty string to start output on next line.
                       msg_header,
                       msg,
                       msg_header])
  logger.info(log_msg)


def AddOptions(parser):
  """Add command line option group for Logging.

  Optional method to add helpful command line options to calling programs. Adds
  the option value "verbose".

  Args:
    parser: OptionParser instance.

  Returns:
    OptionGroup: Users can add additional options to the returned group.
  """
  group = optparse.OptionGroup(parser, title='Logging',
                               description='Logging Configuration Options')
  group.add_option('--log_file',
                   help='Write log messages to specified log file.')
  group.add_option('--skip_console', action='store_true', default=False,
                   help='Do not write log messages to the console.')
  group.add_option('--verbose', dest='verbose', action='store_true',
                   default=False,
                   help='Enable verbose output. Script is quiet by default.')
  return parser.add_option_group(group)