# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re

# We need to import common to be able to import chromite.
import common
from autotest_lib.client.common_lib import global_config
try:
  from chromite.lib import gdata_lib
except ImportError as e:
  gdata_lib = None
  logging.info("Bug filing disabled. %s", e)


BUG_CONFIG_SECTION = 'BUG_REPORTING'


class TestFailure(object):
    """Wrap up all information needed to make an intelligent report about a
    test failure.

    Each TestFailure has a search marker associated with it that can be used to
    find reports of the same error."""


    def __init__(self, build, suite, test, reason):
        """
        @param build The build type, of the form <board>/<milestone>-<release>.
                     ie. x86-mario-release/R25-4321.0.0
        @param suite The name of the suite that this test run was a part of.
        @param test The name of the test that this failure is about.
        @param reason The reason that this test failed.
        """
        self.build = build
        self.suite = suite
        self.test = test
        self.reason = reason


    def bug_title(self):
        """Converts information about a failure into a string appropriate to
        be the title of a bug."""
        return '[%s] %s failed on %s' % (self.suite, self.test, self.build)


    def bug_summary(self):
        """Converts information about this failure into a string appropriate
        to be the summary of this bug. Includes the reason field."""
        return ('This bug has been automatically filed to track the'
            ' failure of %s in the %s suite on %s. It failed with a reason'
            ' of:\n\n%s' % (self.test, self.suite, self.build, self.reason))


    def search_marker(self):
        """When filing a report about this failure, include the returned line in
        the report to provide a way to search for this exact failure."""
        return "%s(%s,%s,%s)" % ('TestFailure', self.suite,
                                    self.test, self.reason)


class Reporter(object):
    """Files external reports about bug failures that happened inside of
    autotest."""


    _project_name = global_config.global_config.get_config_value(
        BUG_CONFIG_SECTION, 'project_name', default='')
    _username = global_config.global_config.get_config_value(
        BUG_CONFIG_SECTION, 'username', default='')
    _password = global_config.global_config.get_config_value(
        BUG_CONFIG_SECTION, 'password', default='')
    _SEARCH_MARKER = 'ANCHOR  '


    def __init__(self):
        if gdata_lib is None:
            logging.warning("Bug filing disabled due to missing imports.")
        if self._project_name and self._username and self._password:
            creds = gdata_lib.Creds()
            creds.SetCreds(self._username, self._password)
            self._tracker = gdata_lib.TrackerComm()
            self._tracker.Connect(creds, self._project_name)
        else:
            logging.error('Tracker auth not set up in shadow_config.ini, '
                          'cannot file bugs.')
            self._tracker = None


    def report(self, failure):
        """
        Report about a failure on the bug tracker. If this failure has already
        happened, post a comment on the existing bug about it occurring again.
        If this is a new failure, create a new bug about it.

        @param failure A TestFailure instance about the failure.
        @return None
        """
        if gdata_lib is None or self._tracker is None:
            logging.info("Can't file %s", failure.bug_title())
            return

        issue = self._find_issue_by_marker(failure.search_marker())
        if issue:
            issue_comment = '%s\n\n%s\n\n%s%s' % (failure.bug_title(),
                                                  failure.bug_summary(),
                                                  self._SEARCH_MARKER,
                                                  failure.search_marker())
            self._tracker.AppendTrackerIssueById(issue.id, issue_comment)
            logging.info("Filed comment on %s", str(issue.id))
        else:
            summary = "%s\n\n%s%s" % (failure.bug_summary(),
                                      self._SEARCH_MARKER,
                                      failure.search_marker())
            issue = gdata_lib.Issue(title=failure.bug_title(),
                summary=summary, labels=['Test-Support'],
                status='Untriaged', owner='')
            bugid = self._tracker.CreateTrackerIssue(issue)
            logging.info("Filing new bug %s", str(bugid))


    def _find_issue_by_marker(self, marker):
        """
        Queries the tracker to find if there is a bug filed for this issue.

        @param marker The marker string to search for to find a duplicate of
                     this issue.
        @return A gdata_lib.Issue instance of the issue that was found, or
                None if no issue was found.
        """

        # This will return at most 25 matches, as that's how the
        # code.google.com API limits this query.
        issues = self._tracker.GetTrackerIssuesByText(
                self._SEARCH_MARKER + marker)

        # TODO(milleral) The tracker doesn't support exact text searching, even
        # with quotes around the search term. Therefore, to hack around this, we
        # need to filter through the results we get back and search for the
        # string ourselves.
        # We could have gotten no results...
        if not issues:
            return None

        # We could have gotten some results, but we need to wade through them
        # to find if there's an actually correct one.
        for issue in issues:
            if marker in issue.summary:
                return issue
            for comment in issue.comments:
                # Sometimes, comment.text is None...
                if comment.text and marker in comment.text:
                    return issue

        # Or, if we make it this far, we have only gotten similar, but not
        # actually matching results.
        return None
