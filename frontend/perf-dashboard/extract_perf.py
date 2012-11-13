#!/usr/bin/env python
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Extracts perf keys from autotest database and writes to local data files.

This script keeps track of the job IDs for which perf keys have already been
extracted on previous runs.  The script only processes those job IDs whose perf
values haven't yet been previously extracted.

Sample usage:
    python extract_perf.py -v

Run with -h to see the full set of command-line options.
"""

import datetime
import logging
import optparse
import os
import re
import simplejson
import sys
import time

import common
from autotest_lib.client.common_lib import global_config
from autotest_lib.server import frontend

try:
    from google.storage.speckle.python.api import rdbms_googleapi
except ImportError:
    # Download the AppEngine SDK if desired from here:
    # https://developers.google.com/appengine/downloads
    rdbms_googleapi = None

try:
    import MySQLdb
except ImportError:
    MySQLdb = None

_GLOBAL_CONF = global_config.global_config
_CONF_SECTION = 'AUTOTEST_WEB'

_MYSQL_READONLY_LOGIN_CREDENTIALS = {
    'host': _GLOBAL_CONF.get_config_value(_CONF_SECTION, 'readonly_host'),
    'user': _GLOBAL_CONF.get_config_value(_CONF_SECTION, 'readonly_user'),
    'passwd': _GLOBAL_CONF.get_config_value(_CONF_SECTION, 'readonly_password'),
    'db': _GLOBAL_CONF.get_config_value(_CONF_SECTION, 'database'),
}

# Paths to files.
_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
_CHART_CONFIG_FILE = os.path.join(_ROOT_DIR, 'croschart_defaults.json')
_DEST_DATA_DIR = os.path.join(_ROOT_DIR, 'data')
_COMPLETED_ID_FILE = os.path.join(_DEST_DATA_DIR, 'job_id_complete.txt')
_CURR_PID_FILE = os.path.join(_DEST_DATA_DIR, __file__ + '.curr_pid.txt')

# Values that can be configured through options.
_NUM_DAYS_BACK = 7  # Ignore perf test runs in database that finished more than
                    # this many days ago.

# Other values that can only be configured here in the code.
_AFE = frontend.AFE()
_PLATFORMS = map(lambda x: x.name, _AFE.get_labels(platform=True))
if 'snow' in _PLATFORMS:
    _PLATFORMS.remove('snow')
    _PLATFORMS.append('daisy')


def get_job_ids(cursor, test_name, oldest_db_lookup_date, completed_ids):
    """Gets all job IDs for the given test name that haven't yet been processed.

    @param cursor: see query_database().
    @param test_name: see query_database().
    @param oldest_db_lookup_date: see query_database().
    @param completed_ids: see query_database().

    @return A list of string job IDs from the database that should be processed.
    """
    query = ('SELECT DISTINCT afe_job_id '
             'FROM tko_perf_view_2 INNER JOIN tko_jobs USING (job_idx) '
             'INNER JOIN tko_status USING (status_idx) WHERE '
             'test_name = %s AND test_finished_time >= %s AND '
             'word != "RUNNING"')
    start_time = time.time()
    cursor.execute(query, (test_name, oldest_db_lookup_date))
    logging.debug('Extracted job IDs in %.2f seconds', time.time() - start_time)
    job_ids = []
    for result_row in cursor:
        job_id = str(result_row[0])
        if job_id not in completed_ids:
            job_ids.append(job_id)
    return job_ids


def write_perf_info_to_disk(job_id, result_dict, test_dir):
    """Writes extracted perf data for the given job ID to disk.

    Also writes the job ID to disk to mark it as having been processed.  Note
    that the written files are not protected against simultaneous access by
    multiple invocations of this script.

    @param job_id: The string job ID.
    @param result_dict: A dictionary of associated perf info to write to disk.
    @param test_dir: The string directory name in which to write perf data.
    """
    result_out = [job_id, result_dict['job_name'], result_dict['platform']]
    perf_items = []
    for perf_key in result_dict['perf_keys']:
        for perf_val in result_dict['perf_keys'][perf_key]:
            perf_items.append((perf_key, perf_val))
    result_out.append(perf_items)
    file_name = os.path.join(test_dir, result_dict['platform'] + '.txt')
    with open(file_name, 'a') as fp:
        fp.write(simplejson.dumps(result_out) + '\n')

    with open(_COMPLETED_ID_FILE, 'a') as fp:
        fp.write(job_id + '\n')


def extract_perf_for_job_id(cursor, job_id, unexpected_job_names, test_dir):
    """Extracts perf data for a given job, then writes to local text files.

    @param cursor: A MySQLdb.cursor object used for interacting with a database.
    @param job_id: The string job ID to process.
    @param unexpected_job_names: A set of job names encountered so far that are
        not associated with a known platform type.
    @param test_dir: The string directory name in which to write perf data.

    @return True, if data for the specified job ID is written to disk, or
        False if not (will be False if the job ID is not associated with a known
        platform type).
    """
    query = ('SELECT job_name,iteration_key,iteration_value '
             'FROM tko_perf_view_2 INNER JOIN tko_jobs USING (job_idx) '
             'WHERE afe_job_id = %s')
    cursor.execute(query, job_id)

    result = {}
    for job_name, key, val in cursor:
        # The job_name string contains the platform name. The platform name is
        # always followed by either "-rX", where X is the milestone number
        # (this is from legacy data in the database), or else it is followed
        # by "-release" (for more recent data in the database).  We do not
        # consider jobs in which the platform name is followed by anything
        # else (in particular, "-paladin" runs).
        #
        # TODO(dennisjeffrey): Simplify the below code once the following bug
        # is addressed to standardize the platform names: crosbug.com/38521.
        match = re.search('(\w+)-r', job_name)
        # Only process jobs for known platforms.
        platform = match.group(1) if match.group(1) in _PLATFORMS else None
        if platform:
            result['job_name'] = job_name
            result['platform'] = platform
            result.setdefault('perf_keys', {})
            if key and val:
                result['perf_keys'].setdefault(key, [])
                result['perf_keys'][key].append(val)
        else:
            unexpected_job_names.add(job_name)

    if 'platform' not in result:
        return False

    write_perf_info_to_disk(job_id, result, test_dir)
    return True


def query_database(cursor, test_name, completed_ids, oldest_db_lookup_date):
    """Queries database for perf values and stores them into local text files.

    This function performs the work only for the specified test case.

    @param cursor: A MySQLdb.cursor object used for interacting with a database.
    @param test_name: The string name of a test case to process.
    @param completed_ids: A set of job IDs that have already been previously
        extracted from the database.
    @param oldest_db_lookup_date: The oldest date (represented as a string) for
        which we want to consider perf values in the database.

    @return The number of new job IDs that have been extracted/processed.
    """
    test_dir = os.path.join(_DEST_DATA_DIR, test_name)
    if not os.path.isdir(test_dir):
        os.makedirs(test_dir)

    # Identify the job IDs that need to be processed.
    job_ids = get_job_ids(cursor, test_name, oldest_db_lookup_date,
                          completed_ids)

    # For each job ID, extract the perf values we need.
    unexpected_job_names = set()
    num_newly_added = 0
    for i, job_id in enumerate(job_ids):
        logging.debug('Processing job %d of %d', i + 1, len(job_ids))

        if extract_perf_for_job_id(cursor, job_id, unexpected_job_names,
                                   test_dir):
            completed_ids.add(job_id)
            num_newly_added += 1

    if unexpected_job_names:
        logging.debug('Job names skipped due to unexpected platform: %s',
                      list(unexpected_job_names))

    return num_newly_added


def extract_new_perf_data(cursor, options):
    """Extracts new perf data from database and writes data to local text files.

    @param cursor: A MySQLdb.cursor object used for interacting with a database.
    @param options: An optparse.OptionParser options object.

    @return The number of new job IDs that have been extracted/processed.
    """
    charts = {}
    with open(_CHART_CONFIG_FILE, 'r') as fp:
        charts = simplejson.loads(fp.read())

    # Compute the oldest date for the perf values that we want to consider.
    oldest_db_lookup_date = (
        datetime.date.today() -
        datetime.timedelta(days=options.num_days_back)).strftime('%Y-%m-%d')

    logging.debug('Extracting job IDs from %s onwards.',
                  oldest_db_lookup_date)

    # Get unique test names.
    test_names = set([c['test_name'] for c in charts])

    # Get list of already-completed job IDs so we don't re-fetch their data.
    completed_ids = set()
    if os.path.isfile(_COMPLETED_ID_FILE):
        with open(_COMPLETED_ID_FILE, 'r') as fp:
            job_ids = map(lambda x: x.strip(), fp.readlines())
            for job_id in job_ids:
                completed_ids.add(job_id)

    num_newly_added = 0
    for i, test_name in enumerate(test_names):
        logging.info('Extracting info for test %d of %d: %s ', i + 1,
                     len(test_names), test_name)

        num_newly_added += query_database(cursor, test_name, completed_ids,
                                          oldest_db_lookup_date)

    return num_newly_added


def cleanup():
    """Cleans up when this script is done."""
    if os.path.isfile(_CURR_PID_FILE):
        os.remove(_CURR_PID_FILE)


def main():
    """Main function."""
    parser = optparse.OptionParser()
    parser.add_option('-n', '--num-days-back', metavar='NUM_DAYS', type='int',
                      default=_NUM_DAYS_BACK,
                      help='Consider only the perf test results that were '
                           'computed within this many days ago (if this script '
                           'is invoked daily, no need to consider history from '
                           'many days back). Defaults to %default days back.')
    parser.add_option('-c', '--cloud-sql', action='store_true', default=False,
                      help='Connect to the chromeos-lab CloudSQL database, '
                           'rather than the original MySQL autotest database.')
    parser.add_option('-v', '--verbose', action='store_true', default=False,
                      help='Use verbose logging.')
    options, _ = parser.parse_args()

    log_level = logging.DEBUG if options.verbose else logging.INFO
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s',
                        level=log_level)

    cursor = None
    if options.cloud_sql:
        # CloudSQL.
        logging.debug('Connecting to CloudSQL...')
        if rdbms_googleapi is None:
            logging.error('CloudSQL requested, but cannot locate CloudSQL '
                          'dependencies. Have you set up CloudSQL on this '
                          'machine?')
            sys.exit(1)
        db = rdbms_googleapi.connect(None,
                                     instance='chromeos-bot:chromeos-lab')
        cursor = db.cursor()
        cursor.execute('USE chromeos_autotest_db')
    else:
        # Autotest MySQL database.
        logging.debug('Connecting to Autotest MySQL database...')
        if MySQLdb is None:
            logging.error('MySQL requested, but cannot locate MySQL '
                          'dependencies. Have you set up MySQL on this '
                          'machine?')
            sys.exit(1)
        db = MySQLdb.connect(**_MYSQL_READONLY_LOGIN_CREDENTIALS)
        cursor = db.cursor()

    logging.debug('Database connection complete.')

    if not os.path.isdir(_DEST_DATA_DIR):
        os.makedirs(_DEST_DATA_DIR)

    common.die_if_already_running(_CURR_PID_FILE, logging)
    num_newly_added = extract_new_perf_data(cursor, options)
    cleanup()
    logging.info('Done! Added info for %d new job IDs', num_newly_added)


if __name__ == '__main__':
    main()
