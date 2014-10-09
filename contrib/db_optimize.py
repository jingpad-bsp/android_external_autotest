#!/usr/bin/python
# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This script will run optimize table for chromeos_autotest_db

This script might have notable impact on the mysql performance as it locks
tables and rebuilds indexes. So be careful when running it on production
systems.
"""

import socket
import subprocess

import common
from autotest_lib.client.common_lib.cros.graphite import stats
from autotest_lib.frontend import database_settings_helper
from autotest_lib.scheduler import email_manager


STATS_KEY = 'db_optimize.%s' % socket.gethostname()
timer = stats.Timer(STATS_KEY)

@timer.decorate
def main_without_exception_handling():
    database_settings = database_settings_helper.get_database_config()
    command = ['mysqlcheck',
               '-o', database_settings['NAME'],
               '-u', database_settings['USER'],
               '-p%s' % database_settings['PASSWORD'],
               ]
    subprocess.check_call(command)


def main():
    try:
        main_without_exception_handling()
    except Exception as e:
        message = 'Uncaught exception; terminating db_optimize.'
        email_manager.manager.log_stacktrace(message)
        logging.exception(message)
        raise
    finally:
        email_manager.manager.send_queued_emails()


if __name__ == '__main__':
    main()
