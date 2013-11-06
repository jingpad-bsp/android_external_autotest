#!/usr/bin/python
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
# pylint: disable-msg=C0111

"""Unit tests for common utility class."""

__author__ = 'dalecurtis@google.com (Dale Curtis)'

import os
import tempfile
import time
import unittest

import common_util


class CommonUtilityTest(unittest.TestCase):

  def testRunCommandFailedCommand(self):
    self.assertRaises(common_util.ChromeOSTestError,
                      common_util.RunCommand, cmd='exit 1')

  def testRunCommandOutput(self):
    self.assertEqual(
        common_util.RunCommand(cmd='echo "    Test    "', output=True),
        'Test')

  def testRunCommandEnvironment(self):
    old_env = os.environ.copy()
    # Ensure variables from local environment are present.
    try:
      user = os.environ['USER']
    except KeyError:
      raise unittest.SkipTest('USER environment variable is not set.')

    self.assertEqual(
        common_util.RunCommand(cmd='echo $test_var-$USER',
                               env={'test_var': 'Test'}, output=True),
        'Test-' + user)
    # Ensure local environment is untampered.
    self.assertEqual(old_env, os.environ)

  def testRunCommandCustomError(self):
    try:
      common_util.RunCommand(cmd='exit 1', error_msg='test')
      self.fail('No exception raised for invalid command.')
    except common_util.ChromeOSTestError, e:
      self.assertEqual(e.args[0], 'test')

  def testRunCommandRetry(self):
    tmp_fd, tmp_fn = tempfile.mkstemp()
    os.close(tmp_fd)

    cmd = 'if [ -f %s ]; then rm %s; exit 1; else exit 0; fi' % (tmp_fn, tmp_fn)
    try:
      common_util.RunCommand(cmd=cmd, error_msg='test', retries=2)
    except common_util.ChromeOSTestError:
      self.fail('Command failed after retry.')

  def testRunCommandRetrySleep(self):
    try_count = 2
    try_sleep = 5

    start_time = time.time()
    try:
      common_util.RunCommand(cmd='exit 1', error_msg='test', retries=try_count,
                             retry_sleep=try_sleep)
      self.fail('No exception raised for invalid command.')
    except common_util.ChromeOSTestError:
      pass

    self.assertTrue(abs((time.time() - start_time)
                        - (try_count * try_sleep)) < 2)

  def testIgnoreErrors(self):
    common_util.RunCommand(cmd='exit 1', ignore_errors=True)

  def testErrorFile(self):
    err_str = '  1 2 3  '
    try:
      common_util.RunCommand(cmd='echo "%s"; exit 1' % err_str, error_file=True)
      self.fail('No exception raised for invalid command.')
    except common_util.ChromeOSTestError, e:
      error_file = e[-1].split()[-1]
      with open(error_file, 'r') as f:
        self.assertEquals(err_str + '\n', f.read())
      os.unlink(error_file)

if __name__ == '__main__':
  unittest.main()
