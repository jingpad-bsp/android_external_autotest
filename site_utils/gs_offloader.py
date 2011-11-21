#!/usr/bin/python
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

__help__ = """Script to archive old Autotest results to Google Storage.

Uses gsutil to archive files to the configured Google Storage bucket. Upon
successful copy, the local results directory is deleted.
"""

__author__ = 'dalecurtis@google.com (Dale Curtis)'

import os
import re
import shutil
import subprocess
import sys
import time


# Google Storage bucket URI to store results in.
GS_URI = 'gs://chromeos-autotest-results'

# Maximum age in days; all older results will be archived.
MAX_AGE_DAYS = 7

# Nice setting for process, the higher the number the lower the priority.
NICENESS = 10

# Location of Autotest results on disk.
RESULTS_DIR = '/usr/local/autotest/results'


def main():
  max_age = MAX_AGE_DAYS
  if len(sys.argv) > 1:
    if sys.argv[1].lower() in ('--help', '-h', '-?'):
      print __help__
      print 'Defaults:'
      print '  Destination: ' + GS_URI
      print '  Max Log Age: %s days' % max_age
      print '  Results path: ' + RESULTS_DIR
      print '\nUsage:'
      print '  ./gs_offloader.py [max log age in days]\n'
      sys.exit(0)
    else:
      max_age = int(sys.argv[1])

  max_age = time.time() - 60 * 60 * 24 * max_age

  # Nice our process (carried to subprocesses) so we don't kill the system.
  os.nice(NICENESS)

  # os.listdir returns relative paths, so change to where we need to be to avoid
  # an os.path.join on each loop.
  os.chdir(RESULTS_DIR)

  # Only pick up directories of the form <job #>-<job user>.
  job_matcher = re.compile('^\d+-\w+')

  # Iterate over all directories in RESULTS_DIR.
  for d in os.listdir('.'):
    if (job_matcher.match(d) and os.path.isdir(d)
        and os.stat(d).st_mtime < max_age):
      # Update command list.
      cmd_list = ['gsutil', '-m', 'cp', '-eR', '-a', 'project-private', d,
                  GS_URI]

      # Save stdout and stderr in case of failure.
      process = subprocess.Popen(
          cmd_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
      output = process.communicate()[0]

      if process.returncode == 0:
        # Everything copied okay, so remove the local directory.
        shutil.rmtree(d)
      else:
        # Copy failed, dump logs and continue to the next directory.
        print output


if __name__ == '__main__':
  main()
