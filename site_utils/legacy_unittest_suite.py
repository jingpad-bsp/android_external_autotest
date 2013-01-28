#!/usr/bin/python
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Unit test suite for downloader."""

__author__ = 'dalecurtis@google.com (Dale Curtis)'

import unittest

from chromeos_test import common_util_test
from chromeos_test import dev_server_test
from chromeos_test import log_util_test
from chromeos_test import test_config_test


def TestSuite():
  suites = []

  suites.append(unittest.TestLoader().loadTestsFromTestCase(
      common_util_test.CommonUtilityTest))

  suites.append(unittest.TestLoader().loadTestsFromTestCase(
      dev_server_test.DevServerTest))

  suites.append(unittest.TestLoader().loadTestsFromTestCase(
      log_util_test.LogUtilityTest))

  suites.append(unittest.TestLoader().loadTestsFromTestCase(
      test_config_test.TestConfigTest))

  return unittest.TestSuite(suites)


if __name__ == '__main__':
  unittest.TextTestRunner(verbosity=2).run(TestSuite())
