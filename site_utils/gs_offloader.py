#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
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

import is_job_complete


# Google Storage bucket URI to store results in.
GS_URI = 'gs://chromeos-autotest-results'

# Set this to True to enable rsync otherwise results are offloaded to GS.
USE_RSYNC = False
RSYNC = "chromeos-sam1:/usr/local/autotest/results/"

# Nice setting for process, the higher the number the lower the priority.
NICENESS = 10

# Location of Autotest results on disk.
RESULTS_DIR = '/usr/local/autotest/results'


def offload_files(results_dir):
  """
  Offload files to Google Storage or the RSYNC host if USE_RSYNC is True.

  @param results_dir: The Autotest results dir to look for dirs to offload.
  """
  # Nice our process (carried to subprocesses) so we don't kill the system.
  os.nice(NICENESS)

  # os.listdir returns relative paths, so change to where we need to be to avoid
  # an os.path.join on each loop.
  os.chdir(RESULTS_DIR)

  # Only pick up directories of the form <job #>-<job user>.
  job_matcher = re.compile('^\d+-\w+')

  # Iterate over all directories in RESULTS_DIR.
  for d in os.listdir('.'):
    print 'Processing %s' % d
    if not job_matcher.match(d):
      print 'Skipping %s' % d
      continue
    job_id = os.path.basename(d).split('-')[0]
    if is_job_complete(job_id) != 0:
      print 'Job %s is not yet complete skipping' % d
      continue
    if (job_matcher.match(d) and os.path.isdir(d)):
      # Update command list.
      print 'Offloading %s' % d
      # The way we collect results, currently, is naive and resulst in a lot of
      # extra data collection. Clear these for now until we can be more
      # exact about what logs we care about. crosbug.com/26784.
      print 'Cleaning'
      cmd_clean = 'find %s -iname chrome_2012\* -exec rm {} \;' % d
      os.system(cmd_clean)

      if USE_RSYNC:
        cmd_list = ['rsync', '-a', d, RSYNC]
      else:
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


def main():
  if len(sys.argv) > 1:
    print __help__
    print 'Defaults:'
    print '  Destination: ' + GS_URI
    print '  Results path: ' + RESULTS_DIR
    print '\nUsage:'
    print '  ./gs_offloader.py\n'
    sys.exit(0)

  offload_files(RESULTS_DIR)


if __name__ == '__main__':
  main()
