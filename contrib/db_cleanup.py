# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime, re, sys, logging

import common
from autotest_lib.tko import db


# Format Appears as: [Date] [Time] - [Msg Level] - [Message]
LOGGING_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
# This regex makes sure the input is in the format of YYYY-MM-DD (2012-02-01)
DATE_FORMAT_REGEX = ('^(19|20)\d\d[- /.](0[1-9]|1[012])[- /.](0[1-9]|[12][0-9]'
                     '|3[01])$')
DELETE_CMD_FORMAT = ('DELETE FROM %s USING %s INNER JOIN %s WHERE %s.%s=%s.%s '
                     'AND %s.%s <= "%s"')
DELETE_WITH_INDIRECTION_FORMAT = ('DELETE FROM %s USING %s INNER JOIN %s INNER'
                                  ' JOIN %s WHERE %s.%s=%s.%s AND %s.%s=%s.%s '
                                  'AND %s.%s <= "%s"')

AFE_JOB_ID = 'afe_job_id'
JOB_ID = 'job_id'
JOB_IDX = 'job_idx'
TEST_IDX = 'test_idx'
WHERE_BEFORE_CLAUSE_FORMAT = '%s <= "%s"'
db = db.db(autocommit=False)


def _delete_table_data_before_date(table_to_delete_from, related_table,
                                   primary_key, date, foreign_key=None,
                                   time_column="started_time",
                                   indirection_table=None,
                                   indirection_primary_key=None,
                                   indirection_foreign_key=None):
    """
    We want a delete statement that will only delete from one table while
    using a related table to find the rows to delete.

    An example mysql command:
    DELETE FROM tko_iteration_result USING tko_iteration_result INNER JOIN
    tko_tests WHERE tko_iteration_result.test_idx=tko_tests.test_idx AND
    tko_tests.started_time <= '2012-02-01';

    There are also tables that require 2 joins to determine which rows we want
    to delete and we determine these rows by joining the table we want to
    delete from with an indirection table to the actual jobs table.

    @param table_to_delete_from: Table whose rows we want to delete.
    @param related_table: Table with the date information we are selecting by.
    @param foreign_key: Foreign key used in table_to_delete_from to reference
                        the related table. If None, the primary_key is used.
    @param primary_key: Primary key in the related table.
    @param date: End date of the information we are trying to delete.
    @param time_column: Column that we want to use to compare the date to.
    @param indirection_table: Table we use to link the data we are trying to
                              delete with the table with the date information.
    @param indirection_primary_key: Key we use to connect the indirection table
                                    to the table we are trying to delete rows
                                    from.
    @param indirection_foreign_key: Key we use to connect the indirection table
                                    to the table with the date information.
    """
    if not foreign_key:
        foreign_key = primary_key
    if not related_table:
        # Deleting from a table directly.
        where = WHERE_BEFORE_CLAUSE_FORMAT % (time_column, date)
        logging.debug('DELETE FROM %s WHERE %s', table_to_delete_from, where)
        db.delete(table_to_delete_from, where)
        return
    if not indirection_table:
        # Deleting using a single JOIN to get the date information.
        sql = DELETE_CMD_FORMAT % (table_to_delete_from, table_to_delete_from,
                                   related_table, table_to_delete_from,
                                   foreign_key, related_table, primary_key,
                                   related_table, time_column, date)
    else:
        # There are cases where we need to JOIN 3 TABLES to determine the rows
        # we want to delete.
        sql = DELETE_WITH_INDIRECTION_FORMAT % (table_to_delete_from,
                table_to_delete_from, indirection_table, related_table,
                table_to_delete_from, foreign_key, indirection_table,
                indirection_primary_key, indirection_table,
                indirection_foreign_key, related_table, primary_key,
                related_table, time_column, date)
    logging.debug('SQL: %s', sql)
    db._exec_sql_with_commit(sql, [], None)


def _subtract_days(date, days_to_subtract):
    """
    Return a date (string) that is 'days' before 'date'

    @param date: date (string) we are subtracting from.
    @param days_to_subtract: days (int) we are subtracting.
    """
    date_obj = datetime.datetime.strptime(date, '%Y-%m-%d')
    difference = date_obj - datetime.timedelta(days=days_to_subtract)
    return difference.strftime('%Y-%m-%d')


def _delete_all_data_before_date(date):
    """
    Delete all the database data before a given date.

    This function focuses predominately on the data for jobs in tko_jobs.
    However not all jobs in afe_jobs are also in tko_jobs.

    Therefore we delete all the afe_job and foreign key relations prior to two
    days before date. Then we do the queries using tko_jobs and these
    tables to ensure all the related information is gone. Even though we are
    repeating deletes on these tables, the second delete will be quick and
    completely thorough in ensuring we clean up all the foreign key
    dependencies correctly.

    @param date: End date of the information we are trying to delete.
    """
    # First cleanup all afe_job related data (prior to 2 days before date).
    # The reason for this is not all afe_jobs may be in tko_jobs.
    afe_date = _subtract_days(date, 2)
    logging.debug('Cleaning up all afe_job data prior to %s.', afe_date)
    _delete_table_data_before_date('afe_aborted_host_queue_entries',
                                   'afe_jobs', 'id', afe_date,
                                   time_column= 'created_on',
                                   foreign_key='queue_entry_id',
                                   indirection_table='afe_host_queue_entries',
                                   indirection_primary_key='id',
                                   indirection_foreign_key='job_id')
    _delete_table_data_before_date('afe_special_tasks', 'afe_jobs', 'id',
                                   afe_date, time_column='created_on',
                                   foreign_key='queue_entry_id',
                                   indirection_table='afe_host_queue_entries',
                                   indirection_primary_key='id',
                                   indirection_foreign_key='job_id')
    _delete_table_data_before_date('afe_host_queue_entries', 'afe_jobs',
                                   'id', afe_date, time_column='created_on',
                                   foreign_key=JOB_ID)
    _delete_table_data_before_date('afe_job_keyvals', 'afe_jobs', 'id',
                                   afe_date, time_column='created_on',
                                   foreign_key=JOB_ID)
    _delete_table_data_before_date('afe_jobs_dependency_labels', 'afe_jobs',
                                   'id', afe_date, time_column='created_on',
                                   foreign_key=JOB_ID)
    _delete_table_data_before_date('afe_jobs', None, None, afe_date,
                                   time_column='created_on')

    # Now go through and clean up all the rows related to tko_jobs prior to
    # date.
    logging.debug('Cleaning up all data related to tko_jobs prior to %s.',
                  date)
    _delete_table_data_before_date('tko_test_attributes', 'tko_tests',
                                   TEST_IDX, date)
    _delete_table_data_before_date('tko_test_labels_tests', 'tko_tests',
                                   TEST_IDX, date, foreign_key= 'test_id')
    _delete_table_data_before_date('tko_iteration_result', 'tko_tests',
                                   TEST_IDX, date)
    _delete_table_data_before_date('tko_iteration_perf_value', 'tko_tests',
                                   TEST_IDX, date)
    _delete_table_data_before_date('tko_iteration_attributes', 'tko_tests',
                                   TEST_IDX, date)
    _delete_table_data_before_date('tko_test_attributes', 'tko_tests',
                                   TEST_IDX, date)
    _delete_table_data_before_date('tko_job_keyvals', 'tko_jobs', JOB_IDX,
                                   date, foreign_key='job_id')
    _delete_table_data_before_date('afe_aborted_host_queue_entries',
                                   'tko_jobs', AFE_JOB_ID, date,
                                   foreign_key='queue_entry_id',
                                   indirection_table='afe_host_queue_entries',
                                   indirection_primary_key='id',
                                   indirection_foreign_key='job_id')
    _delete_table_data_before_date('afe_special_tasks', 'tko_jobs', AFE_JOB_ID,
                                   date, foreign_key='queue_entry_id',
                                   indirection_table='afe_host_queue_entries',
                                   indirection_primary_key='id',
                                   indirection_foreign_key='job_id')
    _delete_table_data_before_date('afe_host_queue_entries', 'tko_jobs',
                                   AFE_JOB_ID, date, foreign_key='job_id')
    _delete_table_data_before_date('afe_job_keyvals', 'tko_jobs', AFE_JOB_ID,
                                   date, foreign_key='job_id')
    _delete_table_data_before_date('afe_jobs_dependency_labels', 'tko_jobs',
                                   AFE_JOB_ID, date, foreign_key='job_id')
    _delete_table_data_before_date('afe_jobs', 'tko_jobs', AFE_JOB_ID,
                                   date, foreign_key='id')
    _delete_table_data_before_date('tko_tests', 'tko_jobs', JOB_IDX, date)
    _delete_table_data_before_date('tko_jobs', None, None, date)


def main():
    logging.basicConfig(level=logging.DEBUG, format=LOGGING_FORMAT)
    if len (sys.argv) != 2:
        print 'USAGE: python db_cleanup_by_date.py [DATE]'
        return
    date = sys.argv[1]
    if not re.match(DATE_FORMAT_REGEX, date):
        print 'DATE must be in yyyy-mm-dd format!'
        return
    try:
        _delete_all_data_before_date(date)
    except:
        logging.debug('Deleting the data failed, rolling back changes')
        db.rollback()
        raise
    logging.debug('Committing')
    db.commit()


if __name__ == '__main__':
    main()
