#!/usr/bin/python
# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import getpass
import mock
import unittest

import common

from autotest_lib.frontend import setup_django_lite_environment
from autotest_lib.server.cros.dynamic_suite import constants
from autotest_lib.site_utils import run_suite


class ResultCollectorUnittest(unittest.TestCase):
    """Runsuite unittest"""

    def setUp(self):
        """Set up test."""
        self.afe = mock.MagicMock()
        self.tko = mock.MagicMock()


    def _build_view(self, test_idx, test_name, subdir, status, afe_job_id,
                    job_name='fake_job_name', reason='fake reason',
                    job_keyvals=None, test_started_time=None,
                    test_finished_time=None):
        """Build a test view using the given fields.

        @param test_idx: An integer representing test_idx.
        @param test_name: A string, e.g. 'dummy_Pass'
        @param subdir: A string representing the subdir field of the test view.
                       e.g. 'dummy_Pass'.
        @param status: A string representing the test status.
                       e.g. 'FAIL', 'PASS'
        @param afe_job_id: An integer representing the afe job id.
        @param job_name: A string representing the job name.
        @param reason: A string representing the reason field of the test view.
        @param job_keyvals: A dictionary stroing the job keyvals.
        @param test_started_time: A string, e.g. '2014-04-12 12:35:33'
        @param test_finished_time: A string, e.g. '2014-04-12 12:35:33'

        @reutrn: A dictionary representing a test view.

        """
        if job_keyvals is None:
            job_keyvals = {}
        return {'test_idx': test_idx, 'test_name': test_name, 'subdir':subdir,
                'status': status, 'afe_job_id': afe_job_id,
                'job_name': job_name, 'reason': reason,
                'job_keyvals': job_keyvals,
                'test_started_time': test_started_time,
                'test_finished_time': test_finished_time}


    def _mock_tko_get_detailed_test_views(self, test_views):
        """Mock tko method get_detailed_test_views call.

        @param test_views: A list of test views that will be returned
                           by get_detailed_test_views.
        """
        return_values = {}
        for v in test_views:
            views_of_job = return_values.setdefault(
                    ('get_detailed_test_views', v['afe_job_id']), [])
            views_of_job.append(v)

        def side_effect(*args, **kwargs):
            """Maps args and kwargs to the mocked return values."""
            key = (kwargs['call'], kwargs['afe_job_id'])
            return return_values[key]

        self.tko.run = mock.MagicMock(side_effect=side_effect)


    def _mock_afe_get_jobs(self, suite_job_id, child_job_ids):
        """Mock afe get_jobs call.

        @param suite_job_id: The afe job id of the suite job.
        @param child_job_ids: A list of job ids of the child jobs.

        """
        return_values = {suite_job_id: []}
        for job_id in child_job_ids:
            new_job = mock.MagicMock()
            new_job.id = job_id
            return_values[suite_job_id].append(new_job)

        def side_effect(*args, **kwargs):
            """Maps args and kwargs to the mocked return values."""
            return return_values[kwargs['parent_job_id']]

        self.afe.get_jobs = mock.MagicMock(side_effect=side_effect)


    def testFetchSuiteTestView(self):
        """Test that it fetches the correct suite test views."""
        suite_job_id = 100
        server_job_view = self._build_view(
                10, 'SERVER_JOB', '----', 'GOOD', suite_job_id)
        test_to_ignore = self._build_view(
                11, 'dummy_Pass', '101-user/host/dummy_Pass',
                'GOOD', suite_job_id)
        test_to_include = self._build_view(
                12, 'dummy_Pass.bluetooth', None, 'TEST_NA', suite_job_id)
        self._mock_tko_get_detailed_test_views(
                [server_job_view, test_to_ignore, test_to_include])
        collector = run_suite.ResultCollector(
                'fake_server', self.afe, self.tko,
                build='fake/build', suite_name='dummy',
                suite_job_id=suite_job_id)
        suite_views = collector._fetch_relevant_test_views_of_suite()
        suite_views = sorted(suite_views, key=lambda view: view['test_idx'])
        # Verify that SERVER_JOB is renamed to 'Suite Prep'
        server_job_view['test_name'] = run_suite.ResultCollector.SUITE_PREP
        # Verify that the test with a subidr is not included.
        expected = [server_job_view, test_to_include]
        self.assertEqual(suite_views, expected)


    def testFetchTestViewOfChildJobs(self):
        """Test that it fetches the correct child test views."""
        build = 'lumpy-release/R36-5788.0.0'
        suite_name = 'my_suite'
        suite_job_id = 100
        good_job_id = 101
        good_job_name = '%s/%s/test_Pass' % (build, suite_name)
        bad_job_id = 102
        bad_job_name = '%s/%s/test_ServerJobFail' % (build, suite_name)

        good_job_server_job = self._build_view(
                20, 'SERVER_JOB', '----', 'GOOD', good_job_id, good_job_name)
        good_job_test = self._build_view(
                21, 'test_Pass', 'fake/subdir', 'GOOD', good_job_id,
                good_job_name)
        bad_job_server_job = self._build_view(
                22, 'SERVER_JOB', '----', 'FAIL', bad_job_id, bad_job_name)
        bad_job_test = self._build_view(
                23, 'test_ServerJobFail', 'fake/subdir', 'GOOD',
                bad_job_id, bad_job_name)
        self._mock_tko_get_detailed_test_views(
                [good_job_server_job, good_job_test,
                 bad_job_server_job, bad_job_test])
        self._mock_afe_get_jobs(suite_job_id, [good_job_id, bad_job_id])
        collector = run_suite.ResultCollector(
                'fake_server', self.afe, self.tko,
                build, suite_name, suite_job_id)
        child_views = collector._fetch_test_views_of_child_jobs()
        child_views = sorted(child_views, key=lambda view: view['test_idx'])
        # Verify that the SERVER_JOB has been renamed properly
        bad_job_server_job['test_name'] = '%s_%s' % (
                good_job_name, 'SERVER_JOB')
        # Verify that failed SERVER_JOB and actual tests are included,
        expected = [good_job_test, bad_job_server_job, bad_job_test]
        self.assertEqual(child_views, expected)
        self.afe.get_jobs.assert_called_once_with(parent_job_id=suite_job_id)


    def testGenerateLinks(self):
        """Test that it generates correct web and buildbot links."""
        suite_job_id = 100
        suite_job_view = self._build_view(
                20, 'Suite prep', '----', 'GOOD', suite_job_id)
        good_test = self._build_view(
                21, 'test_Pass', 'fake/subdir', 'GOOD', 101)
        bad_test = self._build_view(
                23, 'test_Fail', 'fake/subdir', 'FAIL', 102)

        collector = run_suite.ResultCollector(
                'fake_server', self.afe, self.tko,
                'lumpy-release/R36-5788.0.0', 'my_suite', suite_job_id)
        collector._display_names = {20: 'Suite prep', 21: 'test_Pass',
                                    23: 'test_Fail'}
        collector._suite_views = [suite_job_view]
        collector._test_views = [suite_job_view, good_test, bad_test]
        collector._max_testname_width = max(
                [len(v['test_name']) for v in collector._test_views]) + 3
        collector._generate_web_and_buildbot_links()
        URL_PATTERN = run_suite.LogLink._URL_PATTERN
        # expected_web_links is list of (anchor, url) tuples we
        # are expecting.
        expected_web_links = [
                 (collector._display_names[v['test_idx']].ljust(
                         collector._max_testname_width),
                  URL_PATTERN % ('fake_server',
                                '%s-%s' % (v['afe_job_id'], getpass.getuser())))
                 for v in collector._test_views]
        # Verify web links are generated correctly.
        for i in range(len(collector._web_links)):
            expect = expected_web_links[i]
            self.assertEqual(collector._web_links[i].anchor, expect[0])
            self.assertEqual(collector._web_links[i].url, expect[1])

        expected_buildbot_links = [
                 (collector._display_names[v['test_idx']].ljust(
                         collector._max_testname_width),
                  URL_PATTERN % ('fake_server',
                                '%s-%s' % (v['afe_job_id'], getpass.getuser())))
                 for v in collector._test_views if v['status'] != 'GOOD']
        # Verify buildbot links are generated correctly.
        for i in range(len(collector._buildbot_links)):
            expect = expected_buildbot_links[i]
            self.assertEqual(collector._buildbot_links[i].anchor, expect[0])
            self.assertEqual(collector._buildbot_links[i].url, expect[1])


    def _end_to_end_test_helper(
            self, include_bad_test=False, include_warn_test=False,
            include_experimental_bad_test=False, include_timeout_test=False,
            include_self_aborted_test=False, suite_job_status='GOOD'):
        """A helper method for testing ResultCollector end-to-end.

        This method mocks the retrieving of required test views,
        and call ResultCollector.run() to collect the results.

        @param include_bad_test: If True, include a view of a test
                                 which has status 'FAIL'.
        @param include_warn_test: If True, include a view of a test
                                  which has status 'WARN'
        @param include_experimental_bad_test:
                If True, include a view of an experimental test
                which has status 'FAIL'.

        """
        suite_job_id = 100
        good_job_id = 101
        bad_job_id = 102
        warn_job_id = 102
        experimental_bad_job_id = 102
        timeout_job_id = 100
        self_aborted_job_id = 104
        suite_job_keyvals = {
                constants.DOWNLOAD_STARTED_TIME: '2014-04-29 13:14:20',
                constants.PAYLOAD_FINISHED_TIME: '2014-04-29 13:14:25',
                constants.ARTIFACT_FINISHED_TIME: '2014-04-29 13:14:30'}

        server_job_view = self._build_view(
                10, 'SERVER_JOB', '----', suite_job_status, suite_job_id,
                'lumpy-release/R27-3888.0.0-test_suites/control.dummy',
                '', suite_job_keyvals, '2014-04-29 13:14:37',
                '2014-04-29 13:25:27')
        good_test = self._build_view(
                11, 'dummy_Pass', '101-user/host/dummy_Pass', 'GOOD',
                good_job_id, 'lumpy-release/R27-3888.0.0/dummy_Pass',
                '', {}, '2014-04-29 13:15:35', '2014-04-29 13:15:36')
        bad_test = self._build_view(
                12, 'dummy_Fail.Fail', '102-user/host/dummy_Fail.Fail', 'FAIL',
                bad_job_id, 'lumpy-release/R27-3888.0.0/dummy_Fail.Fail',
                'always fail', {}, '2014-04-29 13:16:00',
                '2014-04-29 13:16:02')
        warn_test = self._build_view(
                13, 'dummy_Fail.Warn', '102-user/host/dummy_Fail.Warn', 'WARN',
                warn_job_id, 'lumpy-release/R27-3888.0.0/dummy_Fail.Warn',
                'always warn', {}, '2014-04-29 13:16:00',
                '2014-04-29 13:16:02')
        experimental_bad_test = self._build_view(
                14, 'experimental_dummy_Fail.Fail',
                '102-user/host/dummy_Fail.Fail', 'FAIL',
                experimental_bad_job_id,
                'lumpy-release/R27-3888.0.0/experimental_dummy_Fail.Fail',
                'always fail', {'experimental': 'True'}, '2014-04-29 13:16:06',
                '2014-04-29 13:16:07')
        timeout_test = self._build_view(
                15, 'dummy_Timeout', '', 'ABORT',
                timeout_job_id, 'lumpy-release/R27-3888.0.0/dummy_Timeout',
                'child job did not run', {}, '2014-04-29 13:15:37',
                '2014-04-29 13:15:38')
        self_aborted_test = self._build_view(
                16, 'dummy_Abort', '104-user/host/dummy_Abort', 'ABORT',
                self_aborted_job_id, 'lumpy-release/R27-3888.0.0/dummy_Abort',
                'child job aborted', {}, '2014-04-29 13:15:39',
                '2014-04-29 13:15:40')
        test_views = [server_job_view, good_test]
        child_jobs = set([good_job_id])
        if include_bad_test:
            test_views.append(bad_test)
            child_jobs.add(bad_job_id)
        if include_warn_test:
            test_views.append(warn_test)
            child_jobs.add(warn_job_id)
        if include_experimental_bad_test:
            test_views.append(experimental_bad_test)
            child_jobs.add(experimental_bad_job_id)
        if include_timeout_test:
            test_views.append(timeout_test)
            child_jobs.add(timeout_job_id)
        if include_self_aborted_test:
            test_views.append(self_aborted_test)
            child_jobs.add(self_aborted_job_id)
        self._mock_tko_get_detailed_test_views(test_views)
        self._mock_afe_get_jobs(suite_job_id, child_jobs)
        collector = run_suite.ResultCollector(
               'fake_server', self.afe, self.tko,
               'lumpy-release/R36-5788.0.0', 'dummy', suite_job_id)
        collector.run()
        return collector


    def testEndToEndSuitePass(self):
        """Test it returns code OK when all test pass."""
        collector = self._end_to_end_test_helper()
        self.assertEqual(collector.return_code, run_suite.RETURN_CODES.OK)


    def testEndToEndExperimentalTestFails(self):
        """Test that it returns code OK when only experimental test fails."""
        collector = self._end_to_end_test_helper(
                include_experimental_bad_test=True)
        self.assertEqual(collector.return_code, run_suite.RETURN_CODES.OK)


    def testEndToEndSuiteWarn(self):
        """Test it returns code WARNING when there is a test that warns."""
        collector = self._end_to_end_test_helper(include_warn_test=True)
        self.assertEqual(collector.return_code, run_suite.RETURN_CODES.WARNING)


    def testEndToEndSuiteFail(self):
        """Test it returns code ERROR when there is a test that fails."""
        # Test that it returns ERROR when there is test that fails.
        collector = self._end_to_end_test_helper(include_bad_test=True)
        self.assertEqual(collector.return_code, run_suite.RETURN_CODES.ERROR)

        # Test that it returns ERROR when both experimental and non-experimental
        # test fail.
        collector = self._end_to_end_test_helper(
                include_bad_test=True, include_warn_test=True,
                include_experimental_bad_test=True)
        self.assertEqual(collector.return_code, run_suite.RETURN_CODES.ERROR)


    def testEndToEndSuiteJobFail(self):
        """Test it returns code SUITE_FAILURE when only the suite job failed."""
        collector = self._end_to_end_test_helper(suite_job_status='ABORT')
        self.assertEqual(
                collector.return_code, run_suite.RETURN_CODES.INFRA_FAILURE)

        collector = self._end_to_end_test_helper(suite_job_status='ERROR')
        self.assertEqual(
                collector.return_code, run_suite.RETURN_CODES.INFRA_FAILURE)


    def testEndToEndSuiteTimeout(self):
        """Test it returns correct code when a child job timed out."""
        # a child job timed out, none failed.
        collector = self._end_to_end_test_helper(include_timeout_test=True)
        self.assertEqual(
                collector.return_code, run_suite.RETURN_CODES.SUITE_TIMEOUT)

        # a child job timed out, suite job aborted.
        collector = self._end_to_end_test_helper(
                include_timeout_test=True, suite_job_status='ABORT')
        self.assertEqual(
                collector.return_code, run_suite.RETURN_CODES.SUITE_TIMEOUT)

        # a child job timed out, and one test failed.
        collector = self._end_to_end_test_helper(
                include_bad_test=True, include_timeout_test=True)
        self.assertEqual(collector.return_code, run_suite.RETURN_CODES.ERROR)

        # a child job timed out, and one test warned.
        collector = self._end_to_end_test_helper(
                include_warn_test=True, include_timeout_test=True)
        self.assertEqual(
                collector.return_code, run_suite.RETURN_CODES.SUITE_TIMEOUT)


if __name__ == '__main__':
    unittest.main()
