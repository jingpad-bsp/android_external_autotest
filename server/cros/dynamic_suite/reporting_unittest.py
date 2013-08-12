#!/usr/bin/python
#
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import mox

import common
from autotest_lib.server.cros.dynamic_suite import job_status, reporting
from autotest_lib.site_utils import phapi_lib
from chromite.lib import gdata_lib


class ReportingTest(mox.MoxTestBase):
    """
    Unittests to verify basic control flow for automatic bug filing.
    """

    # fake issue id to use in testing duplicate issues
    _FAKE_ISSUE_ID = 123

    # test report used to generate failure
    test_report = {
        'build':'build-build/R1-1',
        'chrome_version':'28.0',
        'suite':'suite',
        'test':'bad_test',
        'reason':'dreadful_reason',
        'owner':'user',
        'hostname':'myhost',
        'job_id':'myjob',
        'status': 'FAIL',
    }

    bug_template = {
        'labels': ['Cr-Internals-WebRTC'],
        'owner': 'myself',
        'status': 'Fixed',
        'summary': 'This is a short summary',
        'title': None,
    }

    def _get_failure(self):
        """
        Get a TestFailure so we can report it.

        @return: a failure object initialized with values from test_report.
        """

        expected_result = job_status.Status(self.test_report.get('status'),
            self.test_report.get('test'),
            reason=self.test_report.get('reason'),
            job_id=self.test_report.get('job_id'),
            owner=self.test_report.get('owner'),
            hostname=self.test_report.get('hostname'))

        return reporting.TestFailure(self.test_report.get('build'),
            self.test_report.get('chrome_version'),
            self.test_report.get('suite'), expected_result)


    def setUp(self):
        super(ReportingTest, self).setUp()
        self.mox.StubOutClassWithMocks(phapi_lib, 'ProjectHostingApiClient')
        self.mox.StubOutClassWithMocks(gdata_lib, 'TrackerComm')
        self._orig_project_name = reporting.Reporter._project_name
        self._orig_username = reporting.Reporter._username
        self._orig_password = reporting.Reporter._password

        # We want to have some data so that the Reporter doesn't fail at
        # initialization.
        reporting.Reporter._project_name = 'project'
        reporting.Reporter._username = 'username'
        reporting.Reporter._password = 'password'


    def tearDown(self):
        reporting.Reporter._project_name = self._orig_project_name
        reporting.Reporter._username = self._orig_username
        reporting.Reporter._password = self._orig_password
        super(ReportingTest, self).tearDown()


    def testNewIssue(self):
        """
        Add a new issue to the tracker when a matching issue isn't found.

        Confirms that we call CreateTrackerIssue when an Issue search returns None.
        """
        self.mox.StubOutWithMock(reporting.Reporter, '_find_issue_by_marker')
        self.mox.StubOutWithMock(reporting.Reporter, '_get_labels')
        self.mox.StubOutWithMock(reporting.TestFailure, 'bug_summary')

        client = phapi_lib.ProjectHostingApiClient(mox.IgnoreArg(),
                                                   mox.IgnoreArg())
        client.create_issue(mox.IgnoreArg()).AndReturn(
            {'id': self._FAKE_ISSUE_ID})
        reporting.Reporter._get_labels(mox.IgnoreArg()).AndReturn([])
        reporting.Reporter._find_issue_by_marker(mox.IgnoreArg()).AndReturn(
            None)
        reporting.TestFailure.bug_summary().AndReturn('')

        self.mox.ReplayAll()
        bug_id = reporting.Reporter().report(self._get_failure())

        self.assertEqual(bug_id, self._FAKE_ISSUE_ID)


    def testDuplicateIssue(self):
        """
        Dedupe to an existing issue when one is found.

        Confirms that we call AppendTrackerIssueById with the same issue
        returned by the issue search.
        """
        self.mox.StubOutWithMock(reporting.Reporter, '_find_issue_by_marker')
        self.mox.StubOutWithMock(reporting.TestFailure, 'bug_summary')

        issue = self.mox.CreateMock(gdata_lib.Issue)
        issue.id = self._FAKE_ISSUE_ID

        client = phapi_lib.ProjectHostingApiClient(mox.IgnoreArg(),
                                                   mox.IgnoreArg())
        client.update_issue(self._FAKE_ISSUE_ID, mox.IgnoreArg())
        reporting.Reporter._find_issue_by_marker(mox.IgnoreArg()).AndReturn(
            issue)

        reporting.TestFailure.bug_summary().AndReturn('')

        self.mox.ReplayAll()
        bug_id = reporting.Reporter().report(self._get_failure())

        self.assertEqual(bug_id, self._FAKE_ISSUE_ID)


    def testSuiteIssueConfig(self):
        """Test that the suite bug template values are not overridden."""

        def check_suite_options(issue):
            """
            Checks to see if the options specified in bug_template reflect in
            the issue we're about to file, and that the autofiled label was not
            lost in the process.

            @param issue: issue to check labels on.
            """
            assert('autofiled' in issue.labels)
            for k, v in self.bug_template.iteritems():
                if (isinstance(v, list)
                    and all(item in getattr(issue, k) for item in v)):
                    continue
                if v and getattr(issue, k) is not v:
                    return False
            return True

        self.mox.StubOutWithMock(reporting.Reporter, '_find_issue_by_marker')
        self.mox.StubOutWithMock(reporting.Reporter, '_get_labels')
        self.mox.StubOutWithMock(reporting.TestFailure, 'bug_summary')

        reporting.Reporter._find_issue_by_marker(mox.IgnoreArg()).AndReturn(
            None)
        reporting.Reporter._get_labels(mox.IgnoreArg()).AndReturn(['Test'])
        reporting.TestFailure.bug_summary().AndReturn('Summary')

        mock_host = phapi_lib.ProjectHostingApiClient(mox.IgnoreArg(),
                                                      mox.IgnoreArg())
        bug = self.mox.CreateMockAnything()
        mock_host.create_issue(mox.IgnoreArg()).AndReturn(
            {'id': self._FAKE_ISSUE_ID})

        self.mox.ReplayAll()
        bug_id = reporting.Reporter().report(self._get_failure(),
                                             self.bug_template)

        self.assertEqual(bug_id, self._FAKE_ISSUE_ID)


if __name__ == '__main__':
    unittest.main()
