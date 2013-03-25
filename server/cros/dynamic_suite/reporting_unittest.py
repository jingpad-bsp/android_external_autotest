# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mox

from autotest_lib.server.cros.dynamic_suite import reporting
from chromite.lib import gdata_lib


class ReportingTest(mox.MoxTestBase):
    """
    Unittests for the summary field of a new bug.
    """

    # fake issue id to use in testing duplicate issues
    _FAKE_ISSUE_ID = 123

    # test report used to generate failure
    test_report = {
        'build':'build',
        'suite':'suite',
        'test':'bad_test',
        'reason':'dreadful_reason',
        'owner':'user',
        'hostname':'myhost',
        'job_id':'myjob',
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
        return reporting.TestFailure(build=self.test_report.get('build'),
                                     suite=self.test_report.get('suite'),
                                     test=self.test_report.get('test'),
                                     reason=self.test_report.get('reason'),
                                     owner=self.test_report.get('owner'),
                                     hostname=self.test_report.get('hostname'),
                                     job_id=self.test_report.get('job_id'))


    def _stub_out_tracker(self, mock_tracker=None):
        """
        Stub out tracker so a test can proceed without valid credentials.
        """
        self.mox.StubOutWithMock(reporting.Reporter, '_get_tracker')
        reporting.Reporter._get_tracker(mox.IgnoreArg(),
                                        mox.IgnoreArg(),
                                        mox.IgnoreArg()).AndReturn(mock_tracker)
        if mock_tracker is None:
            self.mox.StubOutWithMock(reporting.Reporter, '_check_tracker')
            reporting.Reporter._check_tracker().AndReturn(True)


    def testNewIssue(self):
        """
        Add a new issue to the tracker when a matching issue isn't found.

        Confirms that:
        1. We call CreateTrackerIssue when an Issue search returns None.
        2. The new issue has an 'autofiled' label.
        """

        def check_autofiled_label(issue):
            """
            Checks to see if an issue has the 'autofiled' label.

            @param issue: issue to check labels on.
            """
            return 'autofiled' in issue.labels

        self.mox.StubOutWithMock(reporting.Reporter, '_find_issue_by_marker')
        self.mox.StubOutWithMock(reporting.Reporter, '_get_labels')
        self.mox.StubOutWithMock(reporting.TestFailure, 'bug_summary')

        reporting.Reporter._find_issue_by_marker(mox.IgnoreArg()).AndReturn(
            None)
        reporting.Reporter._get_labels(mox.IgnoreArg()).AndReturn([])
        reporting.TestFailure.bug_summary().AndReturn('')
        tracker = self.mox.CreateMock(gdata_lib.TrackerComm)
        self._stub_out_tracker(tracker)

        self.mox.StubOutWithMock(tracker, 'CreateTrackerIssue')
        tracker.CreateTrackerIssue(mox.Func(check_autofiled_label))

        self.mox.ReplayAll()

        reporting.Reporter().report(self._get_failure())


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

        reporting.Reporter._find_issue_by_marker(mox.IgnoreArg()).AndReturn(
            issue)
        reporting.TestFailure.bug_summary().AndReturn('')
        tracker = self.mox.CreateMock(gdata_lib.TrackerComm)
        self._stub_out_tracker(tracker)

        tracker.AppendTrackerIssueById(self._FAKE_ISSUE_ID, mox.IgnoreArg(),
                                       mox.IgnoreArg())

        self.mox.ReplayAll()

        reporting.Reporter().report(self._get_failure())


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
        tracker = self.mox.CreateMock(gdata_lib.TrackerComm)
        self._stub_out_tracker(tracker)

        self.mox.StubOutWithMock(tracker, 'CreateTrackerIssue')
        tracker.CreateTrackerIssue(mox.Func(check_suite_options))

        self.mox.ReplayAll()

        reporting.Reporter().report(self._get_failure(), self.bug_template)
