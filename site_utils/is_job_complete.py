#!/usr/bin/python

import common
import logging
import sys
from autotest_lib.server import frontend

_AFE = frontend.AFE(debug=False)


class DatabaseAnomaly(Exception):
    """Raised when we observe a database anomaly."""


def is_job_complete(job_id):
    """
    Check if a job is no longer active.

    @param job_id: afe job id like 123 from 123-scottza
    @return: An empty list if the job isn't complete.
             A list containing the job details, if it is.
    """
    return _AFE.run('get_jobs', finished=True, id=job_id)


def get_special_task(job_id):
    """
    Retrieve a special task (Cleanup, Verify, Repair) job from the database.

    @param job_id: job id in string format like '123' from '123-cleanup'

    @return A dictionary representation of the special task.
    """
    # Make sure the job_id is a number.
    if not job_id.isdigit():
        logging.error('Job_id: %s is not a number returning False.', job_id)
        return False

    task = _AFE.run('get_special_tasks', id=job_id)
    if not task:
        raise DatabaseAnomaly('Special Task %s not found in database.' % job_id)
    return task[0]


if __name__ == '__main__':
  if len(sys.argv) != 2:
      print ('Set return status to 0 if job is complete or 1 if it is not.\n'
             'Usage: is_job_complete.py <job_id>')
  else:
      sys.exit(not is_job_complete(sys.argv[1]))
