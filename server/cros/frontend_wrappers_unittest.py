# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for server/cros/frontend_wrappers.py."""

import logging
import mox
import time
import unittest

from autotest_lib.client.common_lib.cros import retry
from autotest_lib.server.cros import frontend_wrappers
from autotest_lib.server import frontend

class FrontendWrappersTest(mox.MoxTestBase):
    """Unit tests for dynamic_suite.Reimager.

    @var _FLAKY_FLAG: for use in tests that need to simulate random failures.
    """

    _FLAKY_FLAG = None

    def setUp(self):
        super(FrontendWrappersTest, self).setUp()
        self._FLAKY_FLAG = False


    def testRetryDecoratorSucceeds(self):
        """Tests that a wrapped function succeeds without retrying."""
        timeout_min = .1
        timeout_sec = timeout_min * 60
        @retry.retry(Exception, timeout_min=timeout_min, delay_sec=1)
        def succeed():
            return True

        deadline = time.time() + timeout_sec
        self.assertTrue(succeed())
        self.assertTrue(time.time() < deadline)


    def testRetryDecoratorFlakySucceeds(self):
        """Tests that a wrapped function can retry and succeed."""
        timeout_min = .1
        timeout_sec = timeout_min * 60
        @retry.retry(Exception, timeout_min=timeout_min, delay_sec=1)
        def flaky_succeed():
            if self._FLAKY_FLAG:
                return True
            self._FLAKY_FLAG = True
            raise Exception

        deadline = time.time() + timeout_sec
        self.assertTrue(flaky_succeed())
        self.assertTrue(time.time() < deadline)


    def testRetryDecoratorFails(self):
        """Tests that a wrapped function retries til the timeout, then fails."""
        timeout_min = .01
        timeout_sec = timeout_min * 60
        @retry.retry(Exception, timeout_min=timeout_min, delay_sec=1)
        def fail():
            raise Exception()

        deadline = time.time() + timeout_sec
        self.assertRaises(Exception, fail)
        self.assertTrue(time.time() >= deadline)
