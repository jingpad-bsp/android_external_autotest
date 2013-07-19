#!/usr/bin/python
#
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import datetime, shelve, sys

import common
from autotest_lib.client.common_lib import mail
from autotest_lib.frontend import setup_django_readonly_environment

# Django and the models are only setup after
# the setup_django_readonly_environment module is imported.
from autotest_lib.frontend.tko import models as tko_models
from autotest_lib.frontend.health import utils


_STORAGE_FILE = 'failure_storage'
# Mark a test as failing too long if it has not passed in this many days
_DAYS_TO_BE_FAILING_TOO_LONG = 60
# Ignore any tests that have not ran in this many days
_DAYS_NOT_RUNNING_CUTOFF = 60
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


def is_valid_test_name(name):
    """
    Returns if a test name is valid or not.

    There is a bunch of entries in the tko_test table that are not actually
    test names. They are there as a side effect of how Autotest uses this
    table.

    Two examples of bad tests names are as follows:
    link-release/R29-4228.0.0/faft_ec/firmware_ECPowerG3_SERVER_JOB
    try_new_image-chormeos1-rack2-host2

    @param name: The candidate test names to check.
    @return True if name is a valid test name and false otherwise.

    """
    return not '/' in name and not name.startswith('try_new_image')


def prepare_last_passes(last_passes):
    """
    Fix up the last passes so they can be used by the system.

    This filters out invalid test names and converts the test names to utf8
    encoding.

    @param last_passes: The dictionary of test_name:last_pass pairs.

    @return: Valid entries in encoded as utf8 strings.
    """
    valid_test_names = filter(is_valid_test_name, last_passes)
    # The shelve module does not accept Unicode objects as keys but does
    # accept utf-8 strings.
    return {name.encode('utf8'): last_passes[name]
            for name in valid_test_names}


def get_recently_ran_test_names():
    """
    Get all the test names from the database that have been recently ran.

    @return a set of the recently ran tests.

    """
    cutoff_delta = datetime.timedelta(_DAYS_NOT_RUNNING_CUTOFF)
    cutoff_date = datetime.datetime.today() - cutoff_delta
    results = tko_models.Test.objects.filter(
        started_time__gte=cutoff_date).values('test').distinct()
    test_names = [test['test'] for test in results]
    valid_test_names = filter(is_valid_test_name, test_names)
    return {test.encode('utf8') for test in valid_test_names}


def get_tests_to_analyze():
    """
    Get all the recently ran tests as well as the last time they have passed.

    The minimum datetime is given as last pass time for tests that have never
    passed.

    @return the dict of test_name:last_finish_time pairs.

    """
    recent_test_names = get_recently_ran_test_names()
    last_passes = utils.get_last_pass_times()
    prepared_passes = prepare_last_passes(last_passes)

    running_passes = {}
    for test, pass_time in prepared_passes.items():
        if test in recent_test_names:
            running_passes[test] = pass_time

    failures_names = recent_test_names.difference(running_passes)
    always_failed = {test: datetime.datetime.min for test in failures_names}
    return dict(always_failed.items() + running_passes.items())


def store_results(tests, storage):
    """
    Store information about tests that have been failing for a long time.


    @param tests: The test_name:time_of_last_pass pairs.
    @param storage: The storage object.

    """
    failing_time_cutoff = datetime.timedelta(_DAYS_TO_BE_FAILING_TOO_LONG)

    today = datetime.datetime.today()
    for test, last_fail in tests.iteritems():
        if today - last_fail >= failing_time_cutoff:
            if test not in storage:
                storage[test] = today
        else:
            try:
                del storage[test]
            except KeyError:
                pass


def email_about_test_failure(storage):
    """
    Send an email about all the tests in the storage object if there are any.

    @param storage: The storage object.

    """
    if storage:
        mail.send(_MAIL_RESULTS_FROM,
                  [_MAIL_RESULTS_TO],
                  [],
                  'Long Failing Tests',
                  'The following tests have been failing for '
                  'at least %s days:\n\n' % (_DAYS_TO_BE_FAILING_TOO_LONG) +
                  '\n'.join(storage.keys()))


def main():
    """
    The script code.

    Allows other python code to import and run this code. This will be more
    important if a nice way to test this code can be determined.

    """
    storage = load_storage()
    tests = get_tests_to_analyze()
    store_results(tests, storage)
    email_about_test_failure(storage)
    save_storage(storage)

    return 0


if __name__ == '__main__':
    sys.exit(main())
