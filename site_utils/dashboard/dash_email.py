# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
# pylint: disable-msg=C0111

"""Handle dashboard analysis and email of test results.

This code specializes the EmailNotifier defined in common_email.py.
DashEmailNotifier is responsible for sending email with test results and
links to aid in troubleshooting test failures.  The parameters of these
emails are generally described in dash_config.json under 'filters'.
"""

__author__ = ['truty@google.com (Mike Truty)']

import logging
import os

import dash_util

from django.shortcuts import render_to_response

from build_info import BuildInfo
from common_email import EmailNotifier

# String resources.
from dash_strings import CHANGELOG_URL
from dash_strings import CHROME_CHANGELOG_URL
from dash_strings import DASHBOARD_MAIN
from dash_strings import EMAIL_TESTS_PER_ROW
from dash_strings import EMAIL_TESTS_SUBJECT
from dash_strings import EMAIL_TRIGGER_CHANGED
from dash_strings import EMAIL_TRIGGER_COMPLETED
from dash_strings import EMAIL_TRIGGER_FAILED
from dash_strings import IMAGE_URLS
from dash_strings import STATUS_FAILED
from dash_strings import STATUS_PASSED
from dash_strings import TEST_CHECKED_PREFIX
from dash_strings import TEST_EMAIL_DIR
from dash_strings import TESTS_STATUS_FILE


def _ParseVersion(build):
  """Extract version from build string. Parses x.x.x.x* and Ryy-x.x.x* forms."""
  build_version = build.rsplit('-', 2)[0]
  if '-' in build_version:
    build_version = build_version.split('-')[1]
  return build_version


class DashEmailNotifier(EmailNotifier):
  """Class to check for failed tests and send emails."""

  def __init__(self, base_dir, netbook, board_type, categories,
               use_sheriffs, extra_emails, trigger, prefix,
               include_experimental=True):
    """Specialize EmailNotifier and set a few of our own variables.

    Args:
      base_dir: Is use to check for previous emails sent.
      netbook: Autotest platform for filtering results: netbook_xxx
      board_type: Chrome OS board to be checked: x86-mario-rc, ...
      categories: Test grouping known by the dashboard code
      use_sheriffs: Indicates send email to the sheriffs
      extra_emails: Add others to receive the email
      trigger: Send email on test finished, failed or result state changed
      prefix: Custom prefix for cache tracking.
      include_experimental: Include failure results for tests marked
                            experimental (Default: True)
    """
    super(DashEmailNotifier, self).__init__(
        base_dir, netbook, board_type, use_sheriffs, extra_emails,
        prefix, TEST_EMAIL_DIR)
    self._categories = categories
    self._trigger = trigger
    self._state_changed = {}
    self._failed_tests = {}
    self._failed_categories = set()
    self._crash_summaries = self._dash_view.GetCrashes().GetTestSummaries()
    self._crashes = {}
    self._previous_build = {}
    self._include_experimental = include_experimental

  def _FindTestFailures(self, build, category, test_name):
    """Scans test details for failures, retrieves artifacts, and finds crashes.

    Helper method for CheckItems which scans the test details for the given test
    in the given category on the given build. Pre-processed test artifacts are
    retrieved from the Autotest server if available.

    Failed tests are saved to self._failed_tests and crashes to self._crashes.

    Logs are added to the test details dictionary under the key 'test_logs'

    Args:
      build: a full build string: 0.8.73.0-r3ed8d12f-b719.
      category: a test group: bvt, regression, desktopui, graphics, ...
      test_name: test_name of Autotest test.

    Returns:
      True if no test failures are found, False if failures were found, and None
      if no details could be loaded for the given test_name.
    """
    # Check test details to see if this test failed.
    test_status = None
    crashes_dict = self._crashes.setdefault(build, {})
    failed_test_dict = self._failed_tests.setdefault(build, {})
    test_details = self.GetTestDetails(category, test_name, build)
    for t in test_details:
      # Skip experimental tests if flag says to do so
      if not self._include_experimental:
        if t.get('experimental', False):
          continue

      # Attempt to load pre-processed test artifacts from server.
      summary = self._crash_summaries.RetrieveTestSummary(t['tag'], test_name)
      if summary and summary.get('crashes'):
        self._failed_categories.add(category)
        # Keep track of crashes indexed by the crashed process and signal.
        for crash in summary['crashes']:
          crashes_dict.setdefault(crash, []).append((test_name, t))

      if t['status'] == 'GOOD':
        if test_status is None:
          test_status = True
        continue

      failed_test_dict.setdefault(test_name, []).append(t)
      self._failed_categories.add(category)
      test_status = False

      # Populate source path to test for processing by Django template later.
      t['test_path'] = self._dash_view.GetAutotestInfo(test_name)[1]

      # Add error logs if they exist.
      if summary:
        t['test_logs'] = summary['log'].strip()

    return test_status

  def _CheckStateChange(self, build, category, test_name, current_test_status):
    """Compares current test status and test status for a previous build.

    Helper method for CheckItems which scans the test details for the given test
    in the given category on the given build and compares that status against
    the status for the current build.

    Args:
      build: a full build string: 0.8.73.0-r3ed8d12f-b719.
      category: a test group: bvt, regression, desktopui, graphics, ...
      test_name: test_name of Autotest test.
      current_test_status: True for success, False for failure, None for none.

    Returns:
      True if the state changed, False otherwise.
    """
    state_changed = True
    # Tests for a board can be run for a build but
    # possibly not for this category.
    previous_details = self.GetTestDetails(category, test_name, build)
    if not current_test_status is None and previous_details:
      # Handle tricky state of multiple test results.
      # Any nongood is considered a failure even among a good.
      previous_test_status = True
      for t in previous_details:
        if not t['status'] == 'GOOD':
          previous_test_status = False
          break
      if current_test_status == previous_test_status:
        state_changed = False
    return state_changed

  def CheckItems(self, items):
    """Finds failed tests and crashes in the specified categories.

    CheckItems checks the latest build for a given category for any crashes or
    test failures. Failing tests are stored in self._failed_tests and crashes
    in self._crashes.

    When the trigger is EMAIL_TRIGGER_CHANGED, the last two builds are compared
    and any differences are recorded in self._state_changed.

    Args:
      items: Tuple of (category list, test_regex) to use for checks.
    """
    categories, test_regex = items
    for category in categories:
      # Retrieve the last two builds for this category.
      builds = self.GetBuilds(category, build_count=2)
      if not builds:
        continue
      build = builds[0]
      if len(builds) > 1:
        self._previous_build[build] = builds[1]

      # Check sentinel file to see if we've already processed this build.
      if self.Checked(category, build):
        continue

      for test_name in self.GetTestNamesInBuild(category, build, test_regex):
        # Scan the test details for failures. Fills out self._failed_tests and
        # self._crashes.
        test_status = self._FindTestFailures(build, category, test_name)

        # For efficiency, only check previous builds when needed.
        if not self._trigger == EMAIL_TRIGGER_CHANGED:
          continue

        # Once state-change has been discovered for any test in the build
        # there is no need to look for more changes.
        state_changed = self._state_changed.setdefault(build, False)
        if state_changed:
          continue

        # It is considered a state-change if no previous build is found.
        if len(builds) < 2:
          self._state_changed[build] = True
        else:
          self._state_changed[build] = self._CheckStateChange(
              builds[1], category, test_name, test_status)

      # Write the sentinel file
      self.SetChecked(category, build)

  def GenerateEmail(self):
    """Send email to aid troubleshooting failed tests.

    Emails are broken into 4 sections:
    1. Intro with summary of failing build and netbook combination.
    2. Table of failing tests.
    3. Inline error logs for perusing.
    4. Inline build log for blame.
    """
    buildinfo = BuildInfo()
    for tpl_build in set(self._failed_tests.keys() + self._crashes.keys()):
      # Sort crashes and failed tests.
      tpl_crashes = sorted(self._crashes.get(tpl_build, None).items())
      tpl_failed_tests = sorted(self._failed_tests.get(tpl_build, None).items())
      if ((self._trigger == EMAIL_TRIGGER_COMPLETED) or
          (self._trigger == EMAIL_TRIGGER_FAILED and
           (tpl_failed_tests or tpl_crashes)) or
          (self._trigger == EMAIL_TRIGGER_CHANGED and
           tpl_build in self._state_changed and
           self._state_changed[tpl_build])):
        tpl_netbook = self._netbook
        tpl_board = self._board_type
        categories = ', '.join(sorted(self._categories))
        if tpl_board in IMAGE_URLS:
          tpl_images_link = dash_util.UrlFix('%s/%s' % (
              IMAGE_URLS[tpl_board].rstrip('/'), _ParseVersion(tpl_build)))
        else:
          tpl_images_link = IMAGE_URLS['default']
        if tpl_build in self._previous_build:
          tpl_changelog_link = dash_util.UrlFix(CHANGELOG_URL % (
              _ParseVersion(self._previous_build[tpl_build]),
              _ParseVersion(tpl_build)))
          old_chrome_version = str(buildinfo.GetChromeVersion(
              tpl_board, self._previous_build[tpl_build])[0])
          new_chrome_version = str(buildinfo.GetChromeVersion(
              tpl_board, tpl_build)[0])
          if old_chrome_version and new_chrome_version:
            tpl_chrome_changelog_link = dash_util.UrlFix(
                CHROME_CHANGELOG_URL % (old_chrome_version, new_chrome_version))

        status = STATUS_PASSED
        if tpl_failed_tests:
          logging.debug(
              'Build %s has %s failed test names to email.',
              tpl_build, len(tpl_failed_tests))
          # Django can't do basic math, so preprocess our failed tests into an
          # array of EMAIL_TESTS_PER_ROW-length arrays containing the failed
          # test data.
          tpl_index = 0
          tpl_split_failed_tests = [[]]
          for name, details in tpl_failed_tests:
            tpl_split_failed_tests[tpl_index].append((name, details[0]))
            if len(tpl_split_failed_tests[tpl_index]) == EMAIL_TESTS_PER_ROW:
              tpl_index += 1
              tpl_split_failed_tests.append([])

        if tpl_failed_tests or tpl_crashes:
          categories = ', '.join(sorted(list(self._failed_categories)))
          status = STATUS_FAILED
        template_file = TESTS_STATUS_FILE % status

        tpl_subject = EMAIL_TESTS_SUBJECT % {
            'board': tpl_board,
            'build': tpl_build,
            'categories': categories,
            'netbook': tpl_netbook[8:].lower(),
            'status': status.lower()}
        body = render_to_response(
            os.path.join('emails', template_file), locals()).content
        self.SendEmail(tpl_subject, body)


def EmailFromConfig(dash_base_dir, dash_view, email_options,
                    prefix=TEST_CHECKED_PREFIX):
  """All the work of checking and sending email.

  Emails test failure summary based on entries in the dash config:
  -For boards/platforms specified
  -For only certain releases if desired
  -For groups (suites)/tests specified
  -To users/sheriffs specified

  Args:
    dash_base_dir: Base dir of the output files.
    dash_view: Reference to our data model.
    email_options: From email_config.json.
    prefix: String to uniquely identify sent emails in the cache.
  """
  triggers = [
      EMAIL_TRIGGER_COMPLETED, EMAIL_TRIGGER_FAILED, EMAIL_TRIGGER_CHANGED]

  for mailer in email_options['resultmail']:
    if not 'platforms' in mailer or not 'filters' in mailer:
      logging.warning('Emailer requires platforms and filters.')
      continue
    for board_prefix, netbooks in mailer['platforms'].iteritems():
      for netbook in netbooks:
        for board in [b for b in dash_view.GetNetbookBoardTypes(netbook)
                      if b.startswith(board_prefix)]:
          for filter_ in mailer['filters']:
            use_sheriffs = filter_.get('sheriffs', False)
            include_experimental = filter_.get('include_experimental', True)
            cc = filter_.get('cc', None)
            if not use_sheriffs and not cc:
              logging.warning('Email requires sheriffs or cc.')
              continue
            trigger = filter_.get('trigger', EMAIL_TRIGGER_FAILED)
            if not trigger in triggers:
              logging.warning('Unknown trigger encountered, using default %s.',
                              EMAIL_TRIGGER_FAILED)
              trigger = EMAIL_TRIGGER_FAILED
            categories = dash_view.GetCategories(netbook, board,
                                                 filter_.get('categories'))
            notifier = DashEmailNotifier(dash_base_dir, netbook, board,
                                         categories, use_sheriffs, cc, trigger,
                                         prefix + trigger,
                                         include_experimental)
            notifier.CheckItems((categories, filter_.get('tests')))
            notifier.GenerateEmail()


def EmailAllFailures(dash_base_dir, dash_view):
  """All the work of checking and sending email.

  Emails test failure summary for any test failure on any board to a common
  Google group.  Subscribers may then choose to receive and filter email
  of their own accord instead of maintaining a config file.

  Re-uses existing emailer code by hand-building a config file surrogate.

  Args:
    dash_base_dir: Base dir of the output files.
    dash_view: Reference to our data model.
  """
  platform_configs = {}
  categories = set()
  for netbook in dash_view.netbooks:
    if not netbook.strip() or not dash_view.GetNetbookBoardTypes(netbook):
      continue
    for board in dash_view.GetNetbookBoardTypes(netbook):
      platform_configs.setdefault(board, []).append(netbook)
      categories |= set(dash_view.GetCategories(netbook, board))

  filter_configs = [{'categories': category,
                     'cc': ['chromeos-automated-test-failures@google.com']}
                    for category in sorted(categories)]

  surrogate_config = {'resultmail': [{'platforms': platform_configs,
                                      'filters': filter_configs}]}
  EmailFromConfig(dash_base_dir, dash_view, surrogate_config,
                  '.tmp_allemailed_')


if __name__ == '__main__':
  print 'Run %s with --mail-generate.' % DASHBOARD_MAIN
