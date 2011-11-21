#!/usr/bin/python
#
# Copyright 2011 Google Inc. All Rights Reserved.

"""A utility library used by other Chrome OS scripts.

Routines to upload chromeos build and autotest job data to appengine based
dashboard.
"""

__author__ = 'ericli@google.com (Eric Li)'

import getpass
import common_util


def UploadBuild(appengine_cfg, board, build, image_archive_url):
  """Upload chromeos build data onto appengine.

  Args:
    appengine_cfg: A dictionary of appengine configuration.
    board: Name of the board.
    build: A build version string.
    image_archive_url: A string of the url location of the image downloaded.

  Raises:
    ChromeOSTestError: If command fails. Message is set by the error_msg
        parameter.
  """
  cmd = ('/usr/local/autotest/cautotest-dashboard/build_poster.py '
         '--board %s --build %s --image_url %s --url %s' %
         (board, build, image_archive_url, appengine_cfg['dash_url']))
  msg = 'Failed to post build (%s-%s) onto appengine.' % (board, build)
  common_util.RemoteCommand(appengine_cfg['upload_from'], getpass.getuser(),
                            cmd, private_key=None, error_msg=msg)


def UploadJob(appengine_cfg, job_id):
  """Upload chromeos autotest job data onto appengine.

  Args:
    appengine_cfg: A dictionary of appengine configuration.
    job_id: afe_job_id from autotest database.

  Raises:
    ChromeOSTestError: If command fails. Message is set by the error_msg
        parameter.
  """
  cmd = ('/usr/local/autotest/cautotest-dashboard/job_poster.py '
         '--job_id %s --url %s' % (job_id, appengine_cfg['dash_url']))
  msg = 'Failed to post job (%s) onto appengine.' % job_id
  common_util.RemoteCommand(appengine_cfg['upload_from'], getpass.getuser(),
                            cmd, private_key=None, error_msg=msg)
