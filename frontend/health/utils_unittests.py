#!/usr/bin/python
#
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime, unittest

import mox

import common
# This must come before the import of utils in order to use the in memory
# database.
from autotest_lib.frontend import setup_django_readonly_environment
from autotest_lib.frontend import setup_test_environment
from autotest_lib.frontend.health import utils
from autotest_lib.frontend.tko import models
from django import test

FAIL_STATUS = models.Status(status_idx=4, word='FAIL')
GOOD_STATUS = models.Status(status_idx=6, word='GOOD')


def add_statuses():
    """
    Save the statuses to the in-memory database.

    These normally exist in the database and the code expects them. However, the
    normal test database setup does not do this for us.
    """
    FAIL_STATUS.save()
    GOOD_STATUS.save()


class GetLastPassTimesTests(mox.MoxTestBase, test.TestCase):
    """Tests the get_last_pass_times function."""

    def setUp(self):
        super(GetLastPassTimesTests, self).setUp()
        setup_test_environment.set_up()
        add_statuses()


    def tearDown(self):
        setup_test_environment.tear_down()
        super(GetLastPassTimesTests, self).tearDown()


    def test_return_most_recent_pass(self):
        """The last time a test passed should be returned."""
        # To add a test entry to the database, the test object has to
        # be instantiated with various other model instances. We give these
        # instances dummy id values.
        job = models.Job(job_idx=1)
        kernel = models.Kernel(kernel_idx=1)
        machine = models.Machine(machine_idx=1)

        early_pass = models.Test(job=job, status=GOOD_STATUS,
                                 kernel=kernel, machine=machine,
                                 test='test',
                                 started_time=datetime.datetime(2012, 1, 1))
        early_pass.save()
        late_pass = models.Test(job=job, status=GOOD_STATUS,
                                kernel=kernel, machine=machine,
                                test='test',
                                started_time=datetime.datetime(2012, 1, 2))
        late_pass.save()

        results = utils.get_last_pass_times()

        self.assertEquals(results, {'test': datetime.datetime(2012, 1, 2)})


    def test_only_return_passing_tests(self):
        """Tests that only tests that have passed at some point are returned."""
        job = models.Job(job_idx=1)
        kernel = models.Kernel(kernel_idx=1)
        machine = models.Machine(machine_idx=1)

        passing_test = models.Test(job=job, status=GOOD_STATUS,
                                   kernel=kernel, machine=machine,
                                   test='passing_test',
                                   started_time=datetime.datetime(2012, 1, 1))
        passing_test.save()
        failing_test = models.Test(job=job, status=FAIL_STATUS,
                                   kernel=kernel, machine=machine,
                                   test='failing_test',
                                   started_time=datetime.datetime(2012, 1, 1))
        failing_test.save()

        results = utils.get_last_pass_times()

        self.assertEquals(results,
                          {'passing_test': datetime.datetime(2012, 1, 1)})


    def test_return_all_passing_tests(self):
        """This function returns all tests that passed at least once."""
        job = models.Job(job_idx=1)
        kernel = models.Kernel(kernel_idx=1)
        machine = models.Machine(machine_idx=1)

        test1 = models.Test(job=job, status=GOOD_STATUS,
                            kernel=kernel, machine=machine,
                            test='test1',
                            started_time=datetime.datetime(2012, 1, 1))
        test1.save()
        test2 = models.Test(job=job, status=GOOD_STATUS,
                            kernel=kernel, machine=machine,
                            test='test2',
                            started_time=datetime.datetime(2012, 1, 2))
        test2.save()

        results = utils.get_last_pass_times()

        self.assertEquals(results, {'test1': datetime.datetime(2012, 1, 1),
                                    'test2': datetime.datetime(2012, 1, 2)})


if __name__ == '__main__':
    unittest.main()
