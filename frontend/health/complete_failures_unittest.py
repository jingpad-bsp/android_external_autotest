#!/usr/bin/python
#
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime, unittest

import mox

import common, complete_failures
from autotest_lib.client.common_lib import mail


class EmailAboutTestFailureTests(mox.MoxTestBase):
    """
    Test the core logic of the comlete_failures.py script.

    The core logic is to send emails only if we have not yet done so for a
    given test before and to take actions if the test has been failing for
    long enough.

    """
    def setUp(self):
        super(EmailAboutTestFailureTests, self).setUp()

        # We need to mock out the send function in all tests or else the
        # emails will be sent out during tests.
        self.mox.StubOutWithMock(mail, 'send')

        self._orignal_too_late = complete_failures._DAYS_TO_BE_FAILING_TOO_LONG


    def tearDown(self):
        complete_failures._DAYS_TO_BE_FAILING_TOO_LONG = self._orignal_too_late


    def test_deal_with_new_failing_test(self):
        """
        Test adding a failing test to the storage.

        We expect the email sending code to be called if it is added.

        """
        # We will want to keep all the datetime logic intact and so we need to
        # keep a reference to the unmocked datetime.
        self.datetime = datetime.datetime
        self.mox.StubOutWithMock(datetime, 'datetime')
        datetime.datetime.today().AndReturn(self.datetime(2012, 1, 1))
        complete_failures._DAYS_TO_BE_FAILING_TOO_LONG = 60

        mail.send(
                'chromeos-test-health@google.com',
                ['chromeos-lab-infrastructure@google.com'],
                [],
                'Long Failing Tests',
                'The following tests have been failing for at '
                'least %i days:\n\ntest'
                    % complete_failures._DAYS_TO_BE_FAILING_TOO_LONG)

        storage = {}

        # The ReplayAll is required or else a mox object sneaks its way into
        # the storage object somehow.
        self.mox.ReplayAll()
        complete_failures.email_about_test_failure(
                {'test': datetime.datetime.min}, storage)

        self.assertEqual(storage['test'], self.datetime(2012, 1, 1))
        self.mox.VerifyAll()


    def test_remove_test_if_it_has_succeeded_recently_enough(self):
        """Test that we remove a passing test from the storage object."""
        storage = {'test': datetime.datetime(2012, 1, 1)}
        complete_failures._DAYS_TO_BE_FAILING_TOO_LONG = 60
        today = datetime.datetime(2012, 4, 10)
        safe_date = datetime.datetime(2012, 4, 9)

        self.mox.StubOutWithMock(datetime, 'datetime')
        datetime.datetime.today().AndReturn(today)

        self.mox.ReplayAll()
        complete_failures.email_about_test_failure({'test': safe_date}, storage)

        self.assertTrue('test' not in storage)
        self.mox.VerifyAll()


    def test_no_crashing_on_test_that_has_never_failed_for_too_long(self):
        """Test that we do not crash for tests that have always passed."""
        storage = {}
        complete_failures._DAYS_TO_BE_FAILING_TOO_LONG = 60
        today = datetime.datetime(2012,4,10)
        safe_date = datetime.datetime(2012,4,9)

        self.mox.StubOutWithMock(datetime, 'datetime')
        datetime.datetime.today().AndReturn(today)

        self.mox.ReplayAll()
        complete_failures.email_about_test_failure({'test': safe_date}, storage)

        self.assertTrue('test' not in storage)
        self.mox.VerifyAll()


    def test_do_not_send_email_if_test_already_in_storage(self):
        """Test only send emails on newly problematic tests."""
        storage = {'test': datetime.datetime(2012, 1, 1)}
        self.datetime = datetime.datetime
        self.mox.StubOutWithMock(datetime, 'datetime')
        datetime.datetime.today().AndReturn(self.datetime(2012, 1, 1))

        self.mox.ReplayAll()
        complete_failures.email_about_test_failure(
                {'test': datetime.datetime.min}, storage)

        self.mox.VerifyAll()


    def test_do_not_delete_if_still_failing(self):
        """Test that an old failing test is not removed from storage."""
        # We will want to keep all the datetime logic intact and so we need to
        # keep a reference to the unmocked datetime.
        self.datetime = datetime.datetime
        today = datetime.datetime(2012, 1, 1)
        self.mox.StubOutWithMock(datetime, 'datetime')
        datetime.datetime.today().AndReturn(today)

        storage = {'test': datetime.datetime.min}

        # The ReplayAll is required or else a mox object sneaks its way into
        # the storage object somehow.
        self.mox.ReplayAll()
        complete_failures.email_about_test_failure(
                {'test': datetime.datetime.min}, storage)

        self.assertTrue('test' in storage)
        self.mox.VerifyAll()


if __name__ == '__main__':
    unittest.main()
