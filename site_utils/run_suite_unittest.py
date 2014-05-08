#!/usr/bin/python
# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import getpass
import mock
import unittest

import common

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
                    test_finished_time=None, invalidates_test_idx=None):
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
        @param invalidates_test_idx: An integer, representing the idx of the
                                     test that has been retried.

        @reutrn: A dictionary representing a test view.

        """
        if job_keyvals is None:
            job_keyvals = {}
        return {'test_idx': test_idx, 'test_name': test_name, 'subdir':subdir,
                'status': status, 'afe_job_id': afe_job_id,
                'job_name': job_name, 'reason': reason,
                'job_keyvals': job_keyvals,
                'test_started_time': test_started_time,
                'test_finished_time': test_finished_time,
                'invalidates_test_idx': invalidates_test_idx}


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
        suite_name = 'dummy'
        build = 'R23-1.1.1.1'
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
        self.assertEqual(suite_views[0].get_testname(),
                         run_suite.TestView.SUITE_PREP)
        # Verify that the test with a subidr is not included.
        self.assertEqual(suite_views[0]['test_idx'], 10)
        self.assertEqual(suite_views[1]['test_idx'], 12)


    def testFetchTestViewOfChildJobs(self):
        """Test that it fetches the correct child test views."""
        build = 'lumpy-release/R36-5788.0.0'
        suite_name = 'my_suite'
        suite_job_id = 100
        invalid_job_id = 101
        invalid_job_name = '%s/%s/test_Pass' % (build, suite_name)
        good_job_id = 102
        good_job_name = '%s/%s/test_Pass' % (build, suite_name)
        bad_job_id = 103
        bad_job_name = '%s/%s/test_ServerJobFail' % (build, suite_name)

        invalid_test = self._build_view(
                19, 'test_Pass_Old', 'fake/subdir',
                'FAIL', invalid_job_id, invalid_job_name)
        good_job_server_job = self._build_view(
                20, 'SERVER_JOB', '----', 'GOOD', good_job_id, good_job_name)
        good_job_test = self._build_view(
                21, 'test_Pass', 'fake/subdir', 'GOOD',
                good_job_id, good_job_name,
                job_keyvals={'retry_original_job_id': invalid_job_id})
        bad_job_server_job = self._build_view(
                22, 'SERVER_JOB', '----', 'FAIL', bad_job_id, bad_job_name)
        bad_job_test = self._build_view(
                23, 'test_ServerJobFail', 'fake/subdir', 'GOOD',
                bad_job_id, bad_job_name)
        self._mock_tko_get_detailed_test_views(
                [good_job_server_job, good_job_test,
                 bad_job_server_job, bad_job_test, invalid_test])
        self._mock_afe_get_jobs(suite_job_id, [good_job_id, bad_job_id])
        collector = run_suite.ResultCollector(
                'fake_server', self.afe, self.tko,
                build, suite_name, suite_job_id)
        child_views, retry_counts = collector._fetch_test_views_of_child_jobs()
        # child_views should contain tests 21, 22, 23
        child_views = sorted(child_views, key=lambda view: view['test_idx'])
        # Verify that the SERVER_JOB has been renamed properly
        self.assertEqual(child_views[1].get_testname(),
                         'test_ServerJobFail_SERVER_JOB')
        # Verify that failed SERVER_JOB and actual invalid tests are included,
        expected = [good_job_test['test_idx'], bad_job_server_job['test_idx'],
                    bad_job_test['test_idx']]
        child_view_ids = [v['test_idx'] for v in child_views]
        self.assertEqual(child_view_ids, expected)
        self.afe.get_jobs.assert_called_once_with(
                parent_job_id=suite_job_id)
        # Verify the retry_counts is calculated correctly
        self.assertEqual(len(retry_counts), 1)
        self.assertEqual(retry_counts[21], 1)


    def testGenerateLinks(self):
        """Test that it generates correct web and buildbot links."""
        suite_job_id = 100
        suite_name = 'my_suite'
        build = 'lumpy-release/R36-5788.0.0'
        suite_job_view = run_suite.TestView(
                self._build_view(
                    20, 'Suite prep', '----', 'GOOD', suite_job_id),
                suite_job_id, suite_name, build)
        good_test = run_suite.TestView(
                self._build_view(
                    21, 'test_Pass', 'fake/subdir', 'GOOD', 101),
                suite_job_id, suite_name, build)
        bad_test = run_suite.TestView(
                self._build_view(
                    23, 'test_Fail', 'fake/subdir', 'FAIL', 102),
                suite_job_id, suite_name, build)

        collector = run_suite.ResultCollector(
                'fake_server', self.afe, self.tko,
                build, suite_name, suite_job_id)
        collector._suite_views = [suite_job_view]
        collector._test_views = [suite_job_view, good_test, bad_test]
        collector._max_testname_width = max(
                [len(v.get_testname()) for v in collector._test_views]) + 3
        collector._generate_web_and_buildbot_links()
        URL_PATTERN = run_suite.LogLink._URL_PATTERN
        # expected_web_links is list of (anchor, url) tuples we
        # are expecting.
        expected_web_links = [
                 (v.get_testname().ljust(collector._max_testname_width),
                  URL_PATTERN % ('fake_server',
                                '%s-%s' % (v['afe_job_id'], getpass.getuser())))
                 for v in collector._test_views]
        # Verify web links are generated correctly.
        for i in range(len(collector._web_links)):
            expect = expected_web_links[i]
            self.assertEqual(collector._web_links[i].anchor, expect[0])
            self.assertEqual(collector._web_links[i].url, expect[1])

        expected_buildbot_links = [
                 (v.get_testname().ljust(collector._max_testname_width),
                  URL_PATTERN % ('fake_server',
                                '%s-%s' % (v['afe_job_id'], getpass.getuser())))
                 for v in collector._test_views if v['status'] != 'GOOD']
        # Verify buildbot links are generated correctly.
        for i in range(len(collector._buildbot_links)):
            expect = expected_buildbot_links[i]
            self.assertEqual(collector._buildbot_links[i].anchor, expect[0])
            self.assertEqual(collector._buildbot_links[i].url, expect[1])
            self.assertEqual(collector._buildbot_links[i].retry_count, 0)


    def _end_to_end_test_helper(
            self, include_bad_test=False, include_warn_test=False,
            include_experimental_bad_test=False, include_timeout_test=False,
            include_self_aborted_test=False,
            include_good_retry=False, include_bad_retry=False,
            suite_job_status='GOOD'):
        """A helper method for testing ResultCollector end-to-end.

        This method mocks the retrieving of required test views,
        and call ResultCollector.run() to collect the results.

        @param include_bad_test:
                If True, include a view of a test which has status 'FAIL'.
        @param include_warn_test:
                If True, include a view of a test which has status 'WARN'
        @param include_experimental_bad_test:
                If True, include a view of an experimental test
                which has status 'FAIL'.
        @param include_timeout_test:
                If True, include a view of a test which was aborted before
                started.
        @param include_self_aborted_test:
                If True, include a view of test which was aborted after
                started.
        @param include_good_retry:
                If True, include a test that passed after retry.
        @param include_bad_retry:
                If True, include a test that failed after retry.

        @returns: A ResultCollector instance.
        """
        suite_job_id = 100
        good_job_id = 101
        bad_job_id = 102
        warn_job_id = 102
        experimental_bad_job_id = 102
        timeout_job_id = 100
        self_aborted_job_id = 104
        good_retry_job_id = 105
        bad_retry_job_id = 106
        invalid_job_id_1 = 90
        invalid_job_id_2 = 91
        suite_name = 'dummy'
        build = 'lumpy-release/R27-3888.0.0'
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
                good_job_id, 'lumpy-release/R27-3888.0.0/dummy/dummy_Pass',
                '', {}, '2014-04-29 13:15:35', '2014-04-29 13:15:36')
        bad_test = self._build_view(
                12, 'dummy_Fail.Fail', '102-user/host/dummy_Fail.Fail', 'FAIL',
                bad_job_id, 'lumpy-release/R27-3888.0.0/dummy/dummy_Fail.Fail',
                'always fail', {}, '2014-04-29 13:16:00',
                '2014-04-29 13:16:02')
        warn_test = self._build_view(
                13, 'dummy_Fail.Warn', '102-user/host/dummy_Fail.Warn', 'WARN',
                warn_job_id, 'lumpy-release/R27-3888.0.0/dummy/dummy_Fail.Warn',
                'always warn', {}, '2014-04-29 13:16:00',
                '2014-04-29 13:16:02')
        experimental_bad_test = self._build_view(
                14, 'experimental_dummy_Fail.Fail',
                '102-user/host/dummy_Fail.Fail', 'FAIL',
                experimental_bad_job_id,
                'lumpy-release/R27-3888.0.0/dummy/experimental_dummy_Fail.Fail',
                'always fail', {'experimental': 'True'}, '2014-04-29 13:16:06',
                '2014-04-29 13:16:07')
        timeout_test = self._build_view(
                15, 'dummy_Timeout', '', 'ABORT',
                timeout_job_id,
                'lumpy-release/R27-3888.0.0/dummy/dummy_Timeout',
                'child job did not run', {}, '2014-04-29 13:15:37',
                '2014-04-29 13:15:38')
        self_aborted_test = self._build_view(
                16, 'dummy_Abort', '104-user/host/dummy_Abort', 'ABORT',
                self_aborted_job_id,
                'lumpy-release/R27-3888.0.0/dummy/dummy_Abort',
                'child job aborted', {}, '2014-04-29 13:15:39',
                '2014-04-29 13:15:40')
        good_retry = self._build_view(
                17, 'dummy_RetryPass', '105-user/host/dummy_RetryPass', 'GOOD',
                good_retry_job_id,
                'lumpy-release/R27-3888.0.0/dummy/dummy_RetryPass',
                '', {'retry_original_job_id': invalid_job_id_1},
                '2014-04-29 13:15:37',
                '2014-04-29 13:15:38', invalidates_test_idx=1)
        bad_retry = self._build_view(
                18, 'dummy_RetryFail', '106-user/host/dummy_RetryFail', 'FAIL',
                bad_retry_job_id,
                'lumpy-release/R27-3888.0.0/dummy/dummy_RetryFail',
                'retry failed', {'retry_original_job_id': invalid_job_id_2},
                '2014-04-29 13:15:39', '2014-04-29 13:15:40',
                invalidates_test_idx=2)
        invalid_test_1 = self._build_view(
                1, 'dummy_RetryPass', '90-user/host/dummy_RetryPass', 'GOOD',
                invalid_job_id_1,
                'lumpy-release/R27-3888.0.0/dummy/dummy_RetryPass',
                'original test failed', {}, '2014-04-29 13:10:00',
                '2014-04-29 13:10:01')
        invalid_test_2 = self._build_view(
                2, 'dummy_RetryFail', '91-user/host/dummy_RetryFail', 'FAIL',
                invalid_job_id_2,
                'lumpy-release/R27-3888.0.0/dummy/dummy_RetryFail',
                'original test failed', {},
                '2014-04-29 13:10:03', '2014-04-29 13:10:04')

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
        if include_good_retry:
            test_views.extend([good_retry, invalid_test_1])
            child_jobs.add(good_retry_job_id)
        if include_bad_retry:
            test_views.extend([bad_retry, invalid_test_2])
            child_jobs.add(bad_retry_job_id)
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

        collector = self._end_to_end_test_helper(include_self_aborted_test=True)
        self.assertEqual(collector.return_code, run_suite.RETURN_CODES.ERROR)


    def testEndToEndSuiteJobFail(self):
        """Test it returns code SUITE_FAILURE when only the suite job failed."""
        collector = self._end_to_end_test_helper(suite_job_status='ABORT')
        self.assertEqual(
                collector.return_code, run_suite.RETURN_CODES.INFRA_FAILURE)

        collector = self._end_to_end_test_helper(suite_job_status='ERROR')
        self.assertEqual(
                collector.return_code, run_suite.RETURN_CODES.INFRA_FAILURE)


    def testEndToEndRetry(self):
        """Test it returns correct code when a test was retried."""
        collector = self._end_to_end_test_helper(include_good_retry=True)
        self.assertEqual(
                collector.return_code, run_suite.RETURN_CODES.WARNING)

        collector = self._end_to_end_test_helper(include_good_retry=True,
                include_self_aborted_test=True)
        self.assertEqual(
                collector.return_code, run_suite.RETURN_CODES.ERROR)

        collector = self._end_to_end_test_helper(include_good_retry=True,
                include_bad_test=True)
        self.assertEqual(
                collector.return_code, run_suite.RETURN_CODES.ERROR)

        collector = self._end_to_end_test_helper(include_bad_retry=True)
        self.assertEqual(
                collector.return_code, run_suite.RETURN_CODES.ERROR)


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
        self.assertEqual(collector.return_code,
                         run_suite.RETURN_CODES.SUITE_TIMEOUT)

        # a child job timed out, and one test was retried.
        collector = self._end_to_end_test_helper(include_good_retry=True,
                include_timeout_test=True)
        self.assertEqual(
                collector.return_code, run_suite.RETURN_CODES.SUITE_TIMEOUT)


if __name__ == '__main__':
    unittest.main()
