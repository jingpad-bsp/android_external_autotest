#!/usr/bin/python
#
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime, unittest

import mox

import common
# This must come before the import of complete_failures in order to use the
# in memory database.
from autotest_lib.frontend import setup_django_readonly_environment
from autotest_lib.frontend import setup_test_environment
import complete_failures
from autotest_lib.client.common_lib import mail
from autotest_lib.frontend.tko import models
from django import test


GOOD_STATUS_IDX = 6
FAIL_STATUS_IDX = 4

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
        super(EmailAboutTestFailureTests, self).tearDown()


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


    def test_do_not_send_email_if_test_already_in_storage(self):
        """Test only send emails on newly problematic tests."""
        storage = {'test': datetime.datetime(2012, 1, 1)}
        self.datetime = datetime.datetime
        self.mox.StubOutWithMock(datetime, 'datetime')
        datetime.datetime.today().AndReturn(self.datetime(2012, 1, 1))

        self.mox.ReplayAll()
        complete_failures.email_about_test_failure(
                {'test': datetime.datetime.min}, storage)


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


class GetLastPassTimesTests(mox.MoxTestBase, test.TestCase):
    """Tests the get_last_pass_times function."""

    def setUp(self):
        super(GetLastPassTimesTests, self).setUp()
        setup_test_environment.set_up()


    def tearDown(self):
        setup_test_environment.tear_down()
        super(GetLastPassTimesTests, self).tearDown()


    def test_return_most_recent_pass(self):
        """The last time a test passed should be returned."""
        # To add a test entry to the database, Django the test object to
        # be instantiated with various other model instances. We give these
        # instances dummy id values.
        job = models.Job(job_idx = 1)
        kernel = models.Kernel(kernel_idx = 1)
        machine = models.Machine(machine_idx = 1)
        success_status = models.Status(status_idx = GOOD_STATUS_IDX)

        early_pass = models.Test(job = job, status = success_status,
                                 kernel = kernel, machine = machine,
                                 test = 'test',
                                 started_time = datetime.datetime(2012, 1, 1))
        early_pass.save()
        late_pass = models.Test(job = job, status = success_status,
                                kernel = kernel, machine = machine,
                                test = 'test',
                                started_time = datetime.datetime(2012, 1, 2))
        late_pass.save()

        results = complete_failures.get_last_pass_times()

        self.assertEquals(results, {'test': datetime.datetime(2012, 1, 2)})


    def test_only_return_passing_tests(self):
        """Tests that only tests that have passed at some point are returned."""
        job = models.Job(job_idx = 1)
        kernel = models.Kernel(kernel_idx = 1)
        machine = models.Machine(machine_idx = 1)
        success_status = models.Status(status_idx = GOOD_STATUS_IDX)
        fail_status = models.Status(status_idx = FAIL_STATUS_IDX)

        passing_test = models.Test(job = job, status = success_status,
                                   kernel = kernel, machine = machine,
                                   test = 'passing_test',
                                   started_time = datetime.datetime(2012, 1, 1))
        passing_test.save()
        failing_test = models.Test(job = job, status = fail_status,
                                   kernel = kernel, machine = machine,
                                   test = 'failing_test',
                                   started_time = datetime.datetime(2012, 1, 1))
        failing_test.save()

        results = complete_failures.get_last_pass_times()

        self.assertEquals(results,
                          {'passing_test': datetime.datetime(2012, 1, 1)})


    def test_return_all_passing_tests(self):
        """This function returns all tests that passed at least once."""
        job = models.Job(job_idx = 1)
        kernel = models.Kernel(kernel_idx = 1)
        machine = models.Machine(machine_idx = 1)
        success_status = models.Status(status_idx = GOOD_STATUS_IDX)

        test1 = models.Test(job = job, status = success_status,
                            kernel = kernel, machine = machine,
                            test = 'test1',
                            started_time = datetime.datetime(2012, 1, 1))
        test1.save()
        test2 = models.Test(job = job, status = success_status,
                            kernel = kernel, machine = machine,
                            test = 'test2',
                            started_time = datetime.datetime(2012, 1, 2))
        test2.save()

        results = complete_failures.get_last_pass_times()

        self.assertEquals(results, {'test1': datetime.datetime(2012, 1, 1),
                                    'test2': datetime.datetime(2012, 1, 2)})


class GetAllTestNamesTests(mox.MoxTestBase, test.TestCase):
    """Tests the get_all_test_names function."""

    def setUp(self):
        super(GetAllTestNamesTests, self).setUp()
        setup_test_environment.set_up()


    def tearDown(self):
        setup_test_environment.tear_down()
        super(GetAllTestNamesTests, self).tearDown()


    def test_return_all_tests(self):
        """Test that the function does as it says it does."""
        job = models.Job(job_idx = 1)
        kernel = models.Kernel(kernel_idx = 1)
        machine = models.Machine(machine_idx = 1)
        success_status = models.Status(status_idx = GOOD_STATUS_IDX)

        test1 = models.Test(job = job, status = success_status,
                            kernel = kernel, machine = machine,
                            test = 'test1',
                            started_time = datetime.datetime(2012, 1, 1))
        test1.save()
        test2 = models.Test(job = job, status = success_status,
                            kernel = kernel, machine = machine,
                            test = 'test2',
                            started_time = datetime.datetime(2012, 1, 2))
        test2.save()

        results = complete_failures.get_all_test_names()

        self.assertEqual(set(results), set(['test1', 'test2']))


    def test_returns_no_duplicate_names(self):
        """Test that each test name appears only once."""
        job = models.Job(job_idx = 1)
        kernel = models.Kernel(kernel_idx = 1)
        machine = models.Machine(machine_idx = 1)
        success_status = models.Status(status_idx = GOOD_STATUS_IDX)

        test = models.Test(job = job, status = success_status,
                           kernel = kernel, machine = machine,
                           test = 'test',
                           started_time = datetime.datetime(2012, 1, 1))
        test.save()
        duplicate = models.Test(job = job, status = success_status,
                                kernel = kernel, machine = machine,
                                test = 'test',
                                started_time = datetime.datetime(2012, 1, 2))
        duplicate.save()

        results = complete_failures.get_all_test_names()

        self.assertEqual(len(results), 1)


class GetTestsToAnalyzeTests(mox.MoxTestBase):
    """Tests the get_tests_to_analyze function."""

    def test_returns_all_test_names(self):
        """Test should return all the test names in the database."""
        self.mox.StubOutWithMock(complete_failures, 'get_last_pass_times')
        self.mox.StubOutWithMock(complete_failures, 'get_all_test_names')

        complete_failures.get_last_pass_times().AndReturn({'passing_test':
            datetime.datetime(2012, 1 ,1)})
        complete_failures.get_all_test_names().AndReturn(['passing_test',
                                                          'failing_test'])
        self.mox.ReplayAll()
        results = complete_failures.get_tests_to_analyze()

        self.assertEqual(set(results.keys()),
                         set(['passing_test', 'failing_test']))


    def test_returns_failing_tests_with_min_datetime(self):
        """Test that never-passed tests are paired with datetime.min."""
        self.mox.StubOutWithMock(complete_failures, 'get_last_pass_times')
        self.mox.StubOutWithMock(complete_failures, 'get_all_test_names')

        complete_failures.get_last_pass_times().AndReturn({})
        complete_failures.get_all_test_names().AndReturn(['test'])

        self.mox.ReplayAll()
        results = complete_failures.get_tests_to_analyze()

        self.assertEqual(results, {'test': datetime.datetime.min})


if __name__ == '__main__':
    unittest.main()
