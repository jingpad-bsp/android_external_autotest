#!/usr/bin/python
#
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import datetime, logging, shelve, sys

import common
from autotest_lib.client.common_lib import mail
from autotest_lib.frontend import setup_django_readonly_environment

# Django and the models are only setup after
# the setup_django_readonly_environment module is imported.
from autotest_lib.frontend.tko import models as tko_models
from django.db import models as django_models


_STORAGE_FILE = 'failure_storage'
_DAYS_TO_BE_FAILING_TOO_LONG = 60
_TEST_PASS_STATUS_INDEX = 6
_MAIL_RESULTS_FROM = 'chromeos-test-health@google.com'
_MAIL_RESULTS_TO = 'chromeos-lab-infrastructure@google.com'


def load_storage():
    """
    Loads the storage object from disk.

    This object keeps track of which tests we have already sent mail about so
    we only send emails when the status of a test changes.

    @return the storage object.

    """
    return shelve.open(_STORAGE_FILE)


def save_storage(storage):
    """
    Saves the storage object to disk.

    @param storage: The storage object to save to disk.

    """
    storage.close()


def get_last_pass_times():
    """
    Get all the tests that have passed and the time they last passed.

    @return the dict of test_name:last_finish_time pairs for tests that have
            passed.

    """
    results = tko_models.Test.objects.values('test').filter(
        status=_TEST_PASS_STATUS_INDEX).annotate(
        last_pass=django_models.Max('started_time'))
    # The shelve module does not accept Unicode objects as keys but utf-8
    # strings are.
    return {result['test'].encode('utf8'): result['last_pass']
            for result in results}


def get_all_test_names():
    """
    Get all the test names from the database.

    @return a list of all the test names.

    """
    test_names = tko_models.Test.objects.values('test').distinct()
    return [test['test'].encode('utf8') for test in test_names]


def get_tests_to_analyze():
    """
    Get all the tests as well as the last time they have passed.

    The minimum datetime is given as last pass time for tests that have never
    passed.

    @return the dict of test_name:last_finish_time pairs.

    """
    last_passes = get_last_pass_times()
    all_test_names = get_all_test_names()
    failures_names = (set(all_test_names) - set(last_passes.keys()))
    always_failed = {test: datetime.datetime.min for test in failures_names}
    return dict(always_failed.items() + last_passes.items())


def email_about_test_failure(tests, storage):
    """
    Send emails based on the last time tests has passed.

    This involves updating the storage and sending an email if a test has
    failed for a long time and we have not already sent an email about that
    test.

    @param tests: The test_name:time_of_last_pass pairs.
    @param storage: The storage object.

    """
    failing_time_cutoff = datetime.timedelta(_DAYS_TO_BE_FAILING_TOO_LONG)
    update_status = []

    today = datetime.datetime.today()
    for test, last_fail in tests.iteritems():
        if today - last_fail >= failing_time_cutoff:
            if test not in storage:
                update_status.append(test)
                storage[test] = today
        else:
            try:
                del storage[test]
            except KeyError:
                pass

    if update_status:
        logging.info('Found %i new failing tests out %i, sending email.',
                     len(update_status),
                     len(tests))
        mail.send(_MAIL_RESULTS_FROM,
                  [_MAIL_RESULTS_TO],
                  [],
                  'Long Failing Tests',
                  'The following tests have been failing for '
                  'at least %s days:\n\n' % (_DAYS_TO_BE_FAILING_TOO_LONG) +
                  '\n'.join(update_status))


def main():
    """
    The script code.

    Allows other python code to import and run this code. This will be more
    important if a nice way to test this code can be determined.

    """
    storage = load_storage()
    tests = get_tests_to_analyze()
    email_about_test_failure(tests, storage)
    save_storage(storage)

    return 0


if __name__ == '__main__':
    sys.exit(main())
