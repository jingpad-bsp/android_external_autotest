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
from autotest_lib.frontend.health import utils
from autotest_lib.client.common_lib import mail
from autotest_lib.frontend.tko import models
from django import test


GOOD_STATUS_IDX = 6

# See complte_failurs_functional_tests.py for why we need this.
class MockDatetime(datetime.datetime):
    """Used to mock out parts of datetime.datetime."""
    pass


class StoreResultsTests(mox.MoxTestBase):
    """Test that entries are properly stored in the storage object."""

    def setUp(self):
        super(StoreResultsTests, self).setUp()
        self._orig_too_long = complete_failures._DAYS_TO_BE_FAILING_TOO_LONG


    def tearDown(self):
        complete_failures._DAYS_TO_BE_FAILING_TOO_LONG = self._orig_too_long
        super(StoreResultsTests, self).tearDown()


    def test_add_failing_test(self):
        """Test adding a failing test to storage."""
        # We will want to keep all the datetime logic intact and so we need to
        # keep a reference to the unmocked datetime.
        self.datetime = datetime.datetime
        self.mox.StubOutWithMock(datetime, 'datetime')
        datetime.datetime.today().AndReturn(self.datetime(2012, 1, 1))
        complete_failures._DAYS_TO_BE_FAILING_TOO_LONG = 60

        storage = {}

        self.mox.ReplayAll()
        complete_failures.store_results(
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
        complete_failures.store_results({'test': safe_date}, storage)

        self.assertTrue('test' not in storage)


    def test_no_crashing_on_test_that_has_never_failed_for_too_long(self):
        """Test that we do not crash for tests that have always passed."""
        storage = {}
        complete_failures._DAYS_TO_BE_FAILING_TOO_LONG = 60
        today = datetime.datetime(2012, 4, 10)
        safe_date = datetime.datetime(2012, 4, 9)

        self.mox.StubOutWithMock(datetime, 'datetime')
        datetime.datetime.today().AndReturn(today)

        self.mox.ReplayAll()
        complete_failures.store_results({'test': safe_date}, storage)

        self.assertTrue('test' not in storage)


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
        complete_failures.store_results(
            {'test': datetime.datetime.min}, storage)

        self.assertTrue('test' in storage)


class EmailAboutTestFailureTests(mox.MoxTestBase):
    """
    Tests that emails are sent about failed tests.

    This currently means an email is sent about all the entries of the
    storage object.

    """
    def setUp(self):
        super(EmailAboutTestFailureTests, self).setUp()

        # We need to mock out the send function in all tests or else the
        # emails will be sent out during tests.
        self.mox.StubOutWithMock(mail, 'send')

        self._orig_too_long = complete_failures._DAYS_TO_BE_FAILING_TOO_LONG


    def tearDown(self):
        complete_failures._DAYS_TO_BE_FAILING_TOO_LONG = self._orig_too_long
        super(EmailAboutTestFailureTests, self).tearDown()


    def test_email_sent_about_all_entries_in_storage(self):
        """Test that the email report mentions all the entries in storage."""
        complete_failures._DAYS_TO_BE_FAILING_TOO_LONG = 60

        mail.send(
                'chromeos-test-health@google.com',
                ['chromeos-lab-infrastructure@google.com'],
                [],
                'Long Failing Tests',
                'The following tests have been failing for at '
                'least %i days:\n\ntest'
                    % complete_failures._DAYS_TO_BE_FAILING_TOO_LONG)

        storage = {'test': datetime.datetime.min}

        # The ReplayAll is required or else a mox object sneaks its way into
        # the storage object somehow.
        self.mox.ReplayAll()
        complete_failures.email_about_test_failure(storage)


class IsValidTestNameTests(test.TestCase):
    """Tests the is_valid_test_name function."""

    def test_returns_true_for_valid_test_name(self):
        """Test that a valid test name returns True."""
        name = 'TestName.TestName'
        self.assertTrue(complete_failures.is_valid_test_name(name))


    def test_returns_false_if_name_has_slash_in_it(self):
        """Test that a name with a slash in it returns False."""
        name = 'path/to/test'
        self.assertFalse(complete_failures.is_valid_test_name(name))


    def test_returns_false_for_try_new_image_entries(self):
        """Test that a name that starts with try_new_image returns False."""
        name = 'try_new_image-blah'
        self.assertFalse(complete_failures.is_valid_test_name(name))


class PrepareLastPassesTests(test.TestCase):
    """Tests the prepare_last_passes function."""

    def setUp(self):
        super(PrepareLastPassesTests, self).setUp()

    def tearDown(self):
        super(PrepareLastPassesTests, self).tearDown()

    def test_does_not_return_invalid_test_names(self):
        """Tests that tests with invalid test names are not returned."""
        results = complete_failures.prepare_last_passes(['invalid_test/name'])

        self.assertEqual(results, {})



class GetRecentlyRanTestNamesTests(mox.MoxTestBase, test.TestCase):
    """Tests the get_recently_ran_test_names function."""

    def setUp(self):
        super(GetRecentlyRanTestNamesTests, self).setUp()
        self.mox.StubOutWithMock(MockDatetime, 'today')
        self.datetime = datetime.datetime
        datetime.datetime = MockDatetime
        setup_test_environment.set_up()
        self._orig_cutoff = complete_failures._DAYS_NOT_RUNNING_CUTOFF


    def tearDown(self):
        datetime.datetime = self.datetime
        complete_failures._DAYS_NOT_RUNNING_CUTOFF = self._orig_cutoff
        setup_test_environment.tear_down()
        super(GetRecentlyRanTestNamesTests, self).tearDown()


    def test_return_all_recently_ran_tests(self):
        """Test that the function does as it says it does."""
        job = models.Job(job_idx=1)
        kernel = models.Kernel(kernel_idx=1)
        machine = models.Machine(machine_idx=1)
        success_status = models.Status(status_idx=GOOD_STATUS_IDX)

        recent = models.Test(job=job, status=success_status,
                             kernel=kernel, machine=machine,
                             test='recent',
                             started_time=self.datetime(2012, 1, 1))
        recent.save()
        old = models.Test(job=job, status=success_status,
                          kernel=kernel, machine=machine,
                          test='old',
                          started_time=self.datetime(2011, 1, 2))
        old.save()

        datetime.datetime.today().AndReturn(self.datetime(2012, 1, 4))
        complete_failures._DAYS_NOT_RUNNING_CUTOFF = 60

        self.mox.ReplayAll()
        results = complete_failures.get_recently_ran_test_names()

        self.assertEqual(set(results), set(['recent']))


    def test_returns_no_duplicate_names(self):
        """Test that each test name appears only once."""
        job = models.Job(job_idx=1)
        kernel = models.Kernel(kernel_idx=1)
        machine = models.Machine(machine_idx=1)
        success_status = models.Status(status_idx=GOOD_STATUS_IDX)

        test = models.Test(job=job, status=success_status,
                           kernel=kernel, machine=machine,
                           test='test',
                           started_time=self.datetime(2012, 1, 1))
        test.save()
        duplicate = models.Test(job=job, status=success_status,
                                kernel=kernel, machine=machine,
                                test='test',
                                started_time=self.datetime(2012, 1, 2))
        duplicate.save()

        datetime.datetime.today().AndReturn(self.datetime(2012, 1, 3))
        complete_failures._DAYS_NOT_RUNNING_CUTOFF = 60

        self.mox.ReplayAll()
        results = complete_failures.get_recently_ran_test_names()

        self.assertEqual(len(results), 1)


class GetTestsToAnalyzeTests(mox.MoxTestBase):
    """Tests the get_tests_to_analyze function."""

    def test_returns_recent_test_names(self):
        """Test should return all the test names in the database."""
        self.mox.StubOutWithMock(utils, 'get_last_pass_times')
        self.mox.StubOutWithMock(complete_failures,
            'get_recently_ran_test_names')

        utils.get_last_pass_times().AndReturn({'passing_test':
            datetime.datetime(2012, 1 ,1),
            'old_passing_test': datetime.datetime(2011, 1, 1)})
        complete_failures.get_recently_ran_test_names().AndReturn(
            {'passing_test',
             'failing_test'})
        self.mox.ReplayAll()
        results = complete_failures.get_tests_to_analyze()

        self.assertEqual(results,
                         {'passing_test': datetime.datetime(2012, 1, 1),
                          'failing_test': datetime.datetime.min})


    def test_returns_failing_tests_with_min_datetime(self):
        """Test that never-passed tests are paired with datetime.min."""
        self.mox.StubOutWithMock(utils, 'get_last_pass_times')
        self.mox.StubOutWithMock(complete_failures,
                                 'get_recently_ran_test_names')

        utils.get_last_pass_times().AndReturn({})
        complete_failures.get_recently_ran_test_names().AndReturn({'test'})

        self.mox.ReplayAll()
        results = complete_failures.get_tests_to_analyze()

        self.assertEqual(results, {'test': datetime.datetime.min})


if __name__ == '__main__':
    unittest.main()
