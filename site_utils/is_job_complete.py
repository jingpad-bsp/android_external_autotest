#!/usr/bin/python

import common
import logging
import _mysql_exceptions
import sys
from autotest_lib.database import database_connection
from autotest_lib.server import frontend

DB_CONFIG_SECTION = 'AUTOTEST_WEB'
SPECIAL_TASKS_SQL_CMD = 'SELECT is_complete FROM afe_special_tasks WHERE id=%s'

_AFE = frontend.AFE(debug=False)
_DATABASE = database_connection.DatabaseConnection(DB_CONFIG_SECTION)
_DATABASE.connect()


def is_job_complete(job_id):
    """
    Check if a job is no longer active.

    @param job_id: afe job id like 123 from 123-scottza
    @return True if job is complete and False if it is not
    """
    if not _AFE.run('get_jobs', finished=True, id=job_id):
        return False

    return True


def is_special_task_complete(job_id):
    """
    Check if a special task (Cleanup, Verify, Repair) job is no longer active.

    @param job_id: job id in string format like '123' from '123-cleanup'

    @return True if a job is complete, and False if it is not.
    """
    # Make sure the job_id is a number.
    if not job_id.isdigit():
        logging.error('Job_id: %s is not a number returning False.', job_id)
        return False
    try:
        query_results = _DATABASE.execute(SPECIAL_TASKS_SQL_CMD, job_id,
                                          try_reconnecting=True)
    except _mysql_exceptions.OperationalError:
        logging.error('Database query failed for job_id: %s.', job_id)
        return False
    # Check if no table rows are returned.
    if not query_results:
        logging.error('Job_id: %s is not a valid special task id.', job_id)
        return False
    # Return the only column in the first (only) row.
    # 1 means done, 0 means running.
    return query_results[0][0]


if __name__ == '__main__':
  if len(sys.argv) != 2:
      print ('Set return status to 0 if job is complete or 1 if it is not.\n'
             'Usage: is_job_complete.py <job_id>')
  else:
      sys.exit(not is_job_complete(sys.argv[1]))
