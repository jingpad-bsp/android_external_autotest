# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mox

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
        'build':'build',
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


    def testNewIssue(self):
        """
        Add a new issue to the tracker when a matching issue isn't found.

        Confirms that we call CreateTrackerIssue when an Issue search returns None.
        """
        self.mox.StubOutWithMock(phapi_lib.ProjectHostingApiClient, '__init__')
        self.mox.StubOutWithMock(reporting.Reporter, '_check_tracker')
        self.mox.StubOutWithMock(reporting.Reporter, '_find_issue_by_marker')
        self.mox.StubOutWithMock(reporting.Reporter, '_get_labels')
        self.mox.StubOutWithMock(reporting.Reporter, '_get_owner')
        self.mox.StubOutWithMock(phapi_lib.ProjectHostingApiClient, 'create_issue')

        phapi_lib.ProjectHostingApiClient.__init__(mox.IgnoreArg(),
                                                   mox.IgnoreArg())
        reporting.Reporter._check_tracker().AndReturn(True)
        reporting.Reporter._find_issue_by_marker(mox.IgnoreArg()).AndReturn(
            None)
        reporting.Reporter._get_labels(mox.IgnoreArg()).AndReturn([])
        reporting.Reporter._check_tracker().AndReturn(True)
        reporting.Reporter._get_owner(mox.IgnoreArg()).AndReturn('')
        phapi_lib.ProjectHostingApiClient.create_issue(
            mox.IgnoreArg()).AndReturn({'id':123})

        self.mox.ReplayAll()

        reporter = reporting.Reporter()
        reporter.phapi_client = self.mox.CreateMock(phapi_lib.ProjectHostingApiClient)
        reporter.report(self._get_failure())


    def testDuplicateIssue(self):
        """
        Dedupe to an existing issue when one is found.

        Confirms that we call AppendTrackerIssueById with the same issue
        returned by the issue search.
        """
        self.mox.StubOutWithMock(phapi_lib.ProjectHostingApiClient, '__init__')
        self.mox.StubOutWithMock(phapi_lib.ProjectHostingApiClient, 'update_issue')
        self.mox.StubOutWithMock(reporting.Reporter, '_find_issue_by_marker')
        self.mox.StubOutWithMock(reporting.Reporter, '_check_tracker')

        phapi_lib.ProjectHostingApiClient.__init__(mox.IgnoreArg(),
                                                   mox.IgnoreArg())
        reporting.Reporter._check_tracker().AndReturn(True)
        issue = self.mox.CreateMock(gdata_lib.Issue)
        issue.id = self._FAKE_ISSUE_ID

        reporting.Reporter._find_issue_by_marker(mox.IgnoreArg()).AndReturn(
            issue)

        phapi_lib.ProjectHostingApiClient.update_issue(
            self._FAKE_ISSUE_ID, mox.IgnoreArg())


        self.mox.ReplayAll()

        reporter = reporting.Reporter()
        reporter.phapi_client = self.mox.CreateMock(phapi_lib.ProjectHostingApiClient)
        reporter.report(self._get_failure())
