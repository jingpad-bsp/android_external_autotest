#!/usr/bin/python
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Helper class for setting up the logging subsystem."""

__author__ = 'dalecurtis@google.com (Dale Curtis)'

import logging
import optparse


def InitializeLogging(verbose=False):
  """Configure the global logger for time/date stamping console output."""
  logging.basicConfig(format='%(asctime)s - %(levelname)s: %(message)s')

  # Enable verbose output if specified.
  if verbose:
    logging.getLogger().setLevel(logging.DEBUG)


def AddOptions(parser):
  """Add command line option group for Logging.

  Optional method to add helpful command line options to calling programs. Adds
  the option value "verbose".

  Args:
    parser: OptionParser instance.
  """
  group = optparse.OptionGroup(parser, 'Logging Options')
  group.add_option('--verbose', dest='verbose', action='store_true',
                   default=False,
                   help='Enable verbose output. Script is quiet by default.')

  parser.add_option_group(group)
