#!/usr/bin/python
#
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

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

# During the tests there is a point where a type check is done on
# datetime.datetime. Unfortunately this means when datetime is mocked it
# horrible failures happen when Django tries to do this check. It is necesarry
# to mock out datetime.datetime completely as it a C class and so cannot have
# parts of itself mocked out. The solution chosen is to create a pure Python
# class that inheirits from datetime.datetime so that the today class method
# can be directly mocked out.
class MockDatetime(datetime.datetime):
    """Used to mock out parts of datetime.datetime."""
    pass


class CompleteFailuresFunctionalTests(mox.MoxTestBase, test.TestCase):
    """
    Does a functional test of the complete_failures script.

    It uses an in-memory database, mocks out the saving and loading of the
    storage object and mocks out the sending of the email. Everything else
    is a full run.

    """

    def setUp(self):
        super(CompleteFailuresFunctionalTests, self).setUp()
        setup_test_environment.set_up()
        # All of our tests will involve mocking out the datetime.today() class
        # method.
        self.mox.StubOutWithMock(MockDatetime, 'today')
        self.datetime = datetime.datetime
        datetime.datetime = MockDatetime
        # We need to mock out the send function in all tests or else the
        # emails will be sent out during tests.
        self.mox.StubOutWithMock(mail, 'send')
        # We also need to mock out the storage access as we do not want
        # to worry about hitting a real file system
        self.mox.StubOutWithMock(complete_failures, 'load_storage')
        self.mox.StubOutWithMock(complete_failures, 'save_storage')

        self._orignal_too_late = complete_failures._DAYS_TO_BE_FAILING_TOO_LONG


    def tearDown(self):
        complete_failures._DAYS_TO_BE_FAILING_TOO_LONG = self._orignal_too_late
        datetime.datetime = self.datetime
        setup_test_environment.tear_down()
        super(CompleteFailuresFunctionalTests, self).tearDown()


    def test(self):
        """Does a basic test of as much of the system as possible."""
        job = models.Job(job_idx = 1)
        kernel = models.Kernel(kernel_idx = 1)
        machine = models.Machine(machine_idx = 1)
        success_status = models.Status(status_idx = GOOD_STATUS_IDX)
        fail_status = models.Status(status_idx = FAIL_STATUS_IDX)

        passing_test = models.Test(job = job, status = success_status,
                                   kernel = kernel, machine = machine,
                                   test = 'test1',
                                   started_time = self.datetime(2012, 1, 1))
        passing_test.save()
        failing_test = models.Test(job = job, status = fail_status,
                                   kernel = kernel, machine = machine,
                                   test = 'test2',
                                   started_time = self.datetime.min)
        failing_test.save()

        complete_failures._DAYS_TO_BE_FAILING_TOO_LONG = 10
        storage = {}
        complete_failures.load_storage().AndReturn(storage)
        MockDatetime.today().AndReturn(self.datetime(2012, 1, 21))
        mail.send('chromeos-test-health@google.com',
                  ['chromeos-lab-infrastructure@google.com'],
                  [],
                  'Long Failing Tests',
                  'The following tests have been failing for at '
                  'least %i days:\n\ntest1\ntest2'
                  % complete_failures._DAYS_TO_BE_FAILING_TOO_LONG)
        complete_failures.save_storage(storage)

        self.mox.ReplayAll()
        complete_failures.main()


if __name__ == '__main__':
    unittest.main()
