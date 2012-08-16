# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for client/common_lib/cros/retry.py."""

import logging
import mox
import time
import unittest

from autotest_lib.client.common_lib.cros import retry
from autotest_lib.client.common_lib import error
from autotest_lib.frontend.afe.json_rpc import proxy

class RetryTest(mox.MoxTestBase):
    """Unit tests for retry decorators.

    @var _FLAKY_FLAG: for use in tests that need to simulate random failures.
    """

    _FLAKY_FLAG = None

    def setUp(self):
        super(RetryTest, self).setUp()
        self._FLAKY_FLAG = False


    def testRetryDecoratorSucceeds(self):
        """Tests that a wrapped function succeeds without retrying."""
        @retry.retry(Exception)
        def succeed():
            return True

        self.mox.StubOutWithMock(time, 'sleep')
        self.mox.ReplayAll()
        self.assertTrue(succeed())


    def testRetryDecoratorFlakySucceeds(self):
        """Tests that a wrapped function can retry and succeed."""
        delay_sec = 10
        @retry.retry(Exception, delay_sec=delay_sec)
        def flaky_succeed():
            if self._FLAKY_FLAG:
                return True
            self._FLAKY_FLAG = True
            raise Exception()

        self.mox.StubOutWithMock(time, 'sleep')
        time.sleep(mox.Func(lambda x: abs(x - delay_sec) <= .5 * delay_sec))
        self.mox.ReplayAll()
        self.assertTrue(flaky_succeed())


    def testRetryDecoratorFails(self):
        """Tests that a wrapped function retries til the timeout, then fails."""
        delay_sec = 10
        @retry.retry(Exception, delay_sec=delay_sec)
        def fail():
            raise Exception()

        self.mox.StubOutWithMock(time, 'sleep')
        time.sleep(mox.Func(lambda x: abs(x - delay_sec) <= .5 * delay_sec))
        self.mox.ReplayAll()
        self.assertRaises(Exception, fail)


    def testRetryDecoratorRaisesCrosDynamicSuiteException(self):
        """Tests that dynamic_suite exceptions raise immediately, no retry."""
        @retry.retry(Exception)
        def fail():
            raise error.ControlFileNotFound()

        self.mox.StubOutWithMock(time, 'sleep')
        self.mox.ReplayAll()
        self.assertRaises(error.ControlFileNotFound, fail)


    def testRetryDecoratorRaisesValidationError(self):
        """Tests that ValidationError raises immediately, no retrying."""
        @retry.retry(Exception)
        def fail():
            raise proxy.ValidationError({'message': 'Exception',
                                         'traceback': 'foo'},
                                        'scary validation message')

        self.mox.StubOutWithMock(time, 'sleep')
        self.mox.ReplayAll()
        self.assertRaises(proxy.ValidationError, fail)
