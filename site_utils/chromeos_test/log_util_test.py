#!/usr/bin/python
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Unit tests for log utility class."""

__author__ = 'dalecurtis@google.com (Dale Curtis)'

import logging
import optparse
import unittest

import log_util


class LogUtilityTest(unittest.TestCase):

  def testVerbose(self):
    log_util.InitializeLogging(verbose=True)
    self.assertEqual(logging.getLogger().getEffectiveLevel(), logging.DEBUG)

  def testNoVerbose(self):
    log_util.InitializeLogging(verbose=False)
    self.assertEqual(logging.getLogger().getEffectiveLevel(), logging.WARNING)

  def testParseOptionsVerbose(self):
    parser = optparse.OptionParser()
    log_util.AddOptions(parser)

    self.assertEqual(parser.parse_args(['--verbose'])[0].verbose, True)

  def testParseOptionsDefaults(self):
    parser = optparse.OptionParser()
    log_util.AddOptions(parser)

    self.assertEqual(parser.parse_args([])[0].verbose, False)


if __name__ == '__main__':
  unittest.main()
