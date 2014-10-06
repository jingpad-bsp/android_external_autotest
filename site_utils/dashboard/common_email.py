# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Common email routines."""

import base64
import commands
import getpass
import hashlib
import logging
import os
import shutil

import dash_util

from build_info import BuildInfo
from dash_view import AutotestDashView

# String resources.
from dash_strings import AUTOTEST_USER
from dash_strings import EMAIL_BUILDS_TO_CHECK
from dash_strings import EMAIL_DIR
from dash_strings import LOCAL_TMP_DIR
from dash_strings import PERFORMANCE_DIR
from dash_strings import WGET_CMD


class EmailNotifier(object):
  """Base class to send emails based on some condition."""

  def __init__(self, base_dir, netbook, board_type, use_sheriffs,
               extra_emails, email_prefix, email_type):
    self._dash_view = AutotestDashView()
    self._netbook = netbook
    self._board_type = board_type
    self._use_sheriffs = use_sheriffs
    self._extra_emails = extra_emails
    self._email_prefix = email_prefix

    self._build_info = BuildInfo()

    self._base_dir = base_dir
    self._cache_dir = os.path.join(base_dir, LOCAL_TMP_DIR, netbook, board_type)
    dash_util.MakeChmodDirs(self._cache_dir)
    self._email_dir = os.path.join(base_dir, EMAIL_DIR, email_type, board_type)
    dash_util.MakeChmodDirs(self._email_dir)
    self._performance_dir = os.path.join(
        base_dir, netbook, board_type, PERFORMANCE_DIR)
    dash_util.MakeChmodDirs(self._performance_dir)

  def GetEmailDir(self):
    return self._email_dir

  def GetPerformanceDir(self):
    return self._performance_dir

  def GetBuilds(self, category, build_count=EMAIL_BUILDS_TO_CHECK):
    return self._dash_view.GetBuilds(
        self._netbook, self._board_type, category)[:build_count]

  def GetTestNamesInBuild(self, category, build, regex):
    return self._dash_view.GetTestNamesInBuild(
        self._netbook, self._board_type, category, build, regex)

  def GetTestDetails(self, category, test_name, build):
    return self._dash_view.GetTestDetails(
        self._netbook, self._board_type, category, test_name, build)

  def GetTestErrorLog(self, log_url):
    diag = dash_util.DebugTiming()
    command = '%s %s' % (WGET_CMD, log_url)
    logging.debug(command)
    error_log = commands.getoutput(command)
    del diag
    return error_log

  def GetEmailFilename(self, category, build):
    return '%s/%s_%s_%s' % (
        self._cache_dir, self._email_prefix, category, build)

  def Checked(self, category, build):
    return os.path.exists(self.GetEmailFilename(category, build))

  def SetChecked(self, category, build):
    dash_util.PruneOldDirsFiles(path=self._cache_dir, dirs=False,
                                older_than_days=20)
    dash_util.SaveHTML(self.GetEmailFilename(category, build), '')

  def FindCurrentSheriffs(self):
    # sheriff.js normally returns a comma separated list of sheriffs,
    # but it may return the following on a weekend:
    #   document.write('None (channel is sheriff)')
    sheriff_from_js = (
        '%s '
        'http://build.chromium.org/buildbot/chromiumos/sheriff.js'
        ' 2>/dev/null | sed "s/.*\'\\(.*\\)\'.*/\\1/"' % WGET_CMD)
    logging.debug(sheriff_from_js)
    out = commands.getoutput(sheriff_from_js)
    if out[:4] == 'None':
      return None
    else:
      return [name.strip() for name in out.split(',') if name.strip()]

  def SendEmail(self, subject, body):
    """Utility sendmail function.

    Wraps the command line call to send email.
    """
    email_to = []
    email_cc = []
    me = getpass.getuser()
    if me == AUTOTEST_USER:
      if self._use_sheriffs:
        sheriffs = self.FindCurrentSheriffs()
        # Sometimes no sheriffs assigned.
        if sheriffs:
          email_to.extend(sheriffs)
        email_cc.append('chromeos-bvt@google.com')
      if self._extra_emails:
        email_to.extend(self._extra_emails)
    else:
      # For debugging email.
      email_to.append(me)
    to = []
    for user in email_to:
      if user.find('@') > -1:
        to.append(user)
      else:
        to.append('%s@chromium.org' % user)
    to = ';'.join(to)
    email_cc = ';'.join(email_cc)

    logging.info(
        "Sending email to: '%s' cc: '%s' with subject: '%s'.",
        to, email_cc, subject)
    p = os.popen('/usr/sbin/sendmail -t', 'w')
    p.write('To: %s\n' % to)
    if email_cc:
      p.write('Cc: %s\n' % email_cc)
    p.write('From: chromeos-automated-test-failures@google.com\n')
    p.write('Subject: %s\n' % subject)
    p.write('Content-Type: text/html')
    p.write('\n')  # blank line separating headers from body
    p.write(body)
    p.write('\n')
    return_code = p.close()
    if return_code is not None:
      logging.error('Sendmail exit status %s', return_code)

  def CheckItems(self, items):
    # Implemented by derived class.
    # Sets state in the class.
    pass

  def GenerateEmail(self):
    # Implemented by derived class.
    # Uses state set by CheckItems.
    pass
