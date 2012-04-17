#!/usr/bin/python

import sys
import common
from autotest_lib.server import frontend

_AFE = frontend.AFE(debug=False)

def is_job_complete(job_id):
    """
    Check if a job is no longer active.

    @param job_id: afe job id like 123 from 123-scottz
    @return True if job is complete and False if it is not
    """
    if not _AFE.run('get_jobs', finished=True, id=job_id):
        return 1

    return 0

if __name__ == '__main__':
  if len(sys.argv) != 2:
      print ('Set return status to 0 if job is complete or 1 if it is not.\n'
             'Usage: is_job_complete.py <job_id>')
  else:
      sys.exit(is_job_complete(sys.argv[1]))
