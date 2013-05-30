#!/usr/bin/python
#
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import datetime, logging, shelve, sys

import common
from autotest_lib.client.common_lib import global_config, mail
from autotest_lib.database import database_connection


_GLOBAL_CONF = global_config.global_config
_CONF_SECTION = 'AUTOTEST_WEB'

_MYSQL_READONLY_LOGIN_CREDENTIALS = {
    'host': _GLOBAL_CONF.get_config_value(_CONF_SECTION, 'readonly_host'),
    'username': _GLOBAL_CONF.get_config_value(_CONF_SECTION, 'readonly_user'),
    'password': _GLOBAL_CONF.get_config_value(
            _CONF_SECTION, 'readonly_password'),
    'db_name': _GLOBAL_CONF.get_config_value(_CONF_SECTION, 'database'),
}

_STORAGE_FILE = 'failure_storage'
_DAYS_TO_BE_FAILING_TOO_LONG = 60
_TEST_PASS_STATUS_INDEX = 6
_MAIL_RESULTS_FROM = 'chromeos-test-health@google.com'
_MAIL_RESULTS_TO = 'chromeos-lab-infrastructure@google.com'


def connect_to_db():
    """
    Create a readonly connection to the Autotest database.

    @return a readonly connection to the Autotest database.

    """
    db = database_connection.DatabaseConnection(_CONF_SECTION)
    db.connect(**_MYSQL_READONLY_LOGIN_CREDENTIALS)
    return db


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


def get_last_pass_times(db):
    """
    Get all the tests that have passed and the time they last passed.

    @param db: The Autotest database connection.
    @return the dict of test_name:last_finish_time pairs for tests that have
            passed.

    """
    query = ('SELECT test, MAX(started_time) FROM tko_tests '
             'WHERE status = %s GROUP BY test' % _TEST_PASS_STATUS_INDEX)

    passed_tests = {result[0]: result[1] for result in db.execute(query)}

    return passed_tests


def get_all_test_names(db):
    """
    Get all the test names from the database.

    @param db: The Autotest database connection.
    @return a list of all the test names.

    """
    query = 'SELECT DISTINCT test FROM tko_tests'
    return [row[0] for row in db.execute(query)]


def get_tests_to_analyze(db):
    """
    Get all the tests as well as the last time they have passed.

    The minimum datetime is given as last pass time for tests that have never
    passed.

    @param db: The Autotest database connection.

    @return the dict of test_name:last_finish_time pairs.

    """
    last_passes = get_last_pass_times(db)
    all_test_names = get_all_test_names(db)
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
    db = connect_to_db()
    storage = load_storage()
    tests = get_tests_to_analyze(db)
    email_about_test_failure(tests, storage)
    save_storage(storage)

    return 0


if __name__ == '__main__':
    sys.exit(main())
