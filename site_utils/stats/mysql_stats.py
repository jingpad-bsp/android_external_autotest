#!/usr/bin/python

# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Queries a MySQL database and emits status metrics to Monarch.

Note: confusingly, 'Innodb_buffer_pool_reads' is actually the cache-misses, not
the number of reads to the buffer pool.  'Innodb_buffer_pool_read_requests'
corresponds to the number of reads the the buffer pool.
"""

import MySQLdb
import time

import common

from chromite.lib import ts_mon_config
from chromite.lib import metrics

from autotest_lib.client.common_lib import global_config


AT_DIR='/usr/local/autotest'
DEFAULT_USER = global_config.global_config.get_config_value(
        'CROS', 'db_backup_user', type=str, default='')
DEFAULT_PASSWD = global_config.global_config.get_config_value(
        'CROS', 'db_backup_password', type=str, default='')
LOOP_INTERVAL = 60
EMITTED_STATUSES = [
    'questions',
    'slow_queries',
    'threads_running',
    'threads_connected',
    'Innodb_buffer_pool_read_requests',
    'Innodb_buffer_pool_reads',
]

def main():
    """Sets up ts_mon and repeatedly queries MySQL stats"""
    ts_mon_config.SetupTsMonGlobalState('mysql_stats', indirect=True)

    db = MySQLdb.connect('localhost', DEFAULT_USER, DEFAULT_PASSWD)
    cursor = db.cursor()
    QueryLoop(cursor)


def QueryLoop(cursor):
    """Queries and emits metrics every LOOP_INTERVAL seconds.

    @param cursor: The mysql command line.
    """
    while True:
        now = time.time()
        QueryAndEmit(cursor)
        time_spent = time.time() - now
        sleep_duration = LOOP_INTERVAL - time_spent
        time.sleep(max(0, sleep_duration))


def QueryAndEmit(cursor):
    """Queries MySQL for important stats and emits Monarch metrics

    @param cursor: The mysql command line.
    """
    def GetStatus(s):
        """Get the status variable from database.

        @param s: Name of the status variable.
        @returns The mysql query result.
        """
        return cursor.execute('SHOW GLOBAL STATUS LIKE "%s";' % s)

    for status in EMITTED_STATUSES:
        metrics.Counter('chromeos/autotest/afe_db/%s' % status.lower()).set(
            GetStatus(status))

    pages_free = GetStatus('Innodb_buffer_pool_pages_free')
    pages_total = GetStatus('Innodb_buffer_pool_pages_total')

    metrics.Gauge('chromeos/autotest/afe_db/buffer_pool_pages').set(
        pages_free, fields={'used': False})

    metrics.Gauge('chromeos/autotest/afe_db/buffer_pool_pages').set(
        pages_total - pages_free, fields={'used': True})


if __name__ == '__main__':
  main()
