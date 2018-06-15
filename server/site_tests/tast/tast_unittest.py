#!/usr/bin/python
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import os
import shutil
import tempfile
import unittest

import dateutil.parser

import common
import tast

from autotest_lib.client.common_lib import base_job
from autotest_lib.client.common_lib import error


# Arbitrary base time to use in tests.
BASE_TIME = dateutil.parser.parse('2018-01-01T00:00:00Z')

# Arbitrary fixed time to use in place of time.time() when running tests.
NOW = BASE_TIME + datetime.timedelta(0, 60)


class TastTest(unittest.TestCase):
    """Tests the tast.tast Autotest server test.

    This unit test verifies interactions between the tast.py Autotest server
    test and the 'tast' executable that's actually responsible for running
    individual Tast tests and reporting their results. To do that, it sets up a
    fake environment in which it can run the Autotest test, including a fake
    implementation of the 'tast' executable provided by testdata/fake_tast.py.
    """

    # Arbitrary data to pass to the tast command.
    HOST = 'dut.example.net'
    PORT = 22
    TEST_PATTERNS = ['(bvt)']
    MAX_RUN_SEC = 300

    def setUp(self):
        self._temp_dir = tempfile.mkdtemp('.tast_unittest')

        def make_subdir(subdir):
            # pylint: disable=missing-docstring
            path = os.path.join(self._temp_dir, subdir)
            os.mkdir(path)
            return path

        self._job = FakeServerJob(make_subdir('job'))
        self._bin_dir = make_subdir('bin')
        self._out_dir = make_subdir('out')
        self._root_dir = make_subdir('root')
        self._set_up_root()

        self._test = tast.tast(self._job, self._bin_dir, self._out_dir)

        self._test_patterns = []
        self._tast_commands = {}

    def tearDown(self):
        shutil.rmtree(self._temp_dir)

    def _get_path_in_root(self, orig_path):
        """Appends a path to self._root_dir (which stores Tast-related files).

        @param orig_path: Path to append, e.g. '/usr/bin/tast'.
        @return: Path within the root dir, e.g. '/path/to/root/usr/bin/tast'.
        """
        return os.path.join(self._root_dir, os.path.relpath(orig_path, '/'))

    def _set_up_root(self, ssp=False):
        """Creates Tast-related files and dirs within self._root_dir.

        @param ssp: If True, install files to locations used with Server-Side
            Packaging. Otherwise, install to locations used by Portage packages.
        """
        def create_file(orig_dest, src=None):
            """Creates a file under self._root_dir.

            @param orig_dest: Original absolute path, e.g. "/usr/bin/tast".
            @param src: Absolute path to file to copy, or none to create empty.
            @return: Absolute path to created file.
            """
            dest = self._get_path_in_root(orig_dest)
            if not os.path.exists(os.path.dirname(dest)):
                os.makedirs(os.path.dirname(dest))
            if src:
                shutil.copyfile(src, dest)
                shutil.copymode(src, dest)
            else:
                open(dest, 'a').close()
            return dest

        # Copy fake_tast.py to the usual location for the 'tast' executable.
        # The remote bundle dir and remote_test_runner just need to exist so
        # tast.py can find them; their contents don't matter since fake_tast.py
        # won't actually use them.
        self._tast_path = create_file(
                tast.tast._SSP_TAST_PATH if ssp else tast.tast._TAST_PATH,
                os.path.join(os.path.dirname(os.path.realpath(__file__)),
                             'testdata', 'fake_tast.py'))
        self._remote_bundle_dir = os.path.dirname(
                create_file(os.path.join(tast.tast._SSP_REMOTE_BUNDLE_DIR if ssp
                                         else tast.tast._REMOTE_BUNDLE_DIR,
                                         'fake')))
        self._remote_test_runner_path = create_file(
                tast.tast._SSP_REMOTE_TEST_RUNNER_PATH if ssp
                else tast.tast._REMOTE_TEST_RUNNER_PATH)

    def _init_tast_commands(self, tests):
        """Sets fake_tast.py's behavior for 'list' and 'run' commands.

        @param list_tests: List of test dicts from make_test that should be
            printed in response to 'list' commands.
        @param run_results: List of test result dicts from make_test_result that
            should be written in response to 'run' commands.
        """
        list_args = [
            'build=False',
            'patterns=%s' % self.TEST_PATTERNS,
            'remotebundledir=' + self._remote_bundle_dir,
            'remoterunner=' + self._remote_test_runner_path,
            'target=%s:%d' % (self.HOST, self.PORT),
            'verbose=True',
        ]
        run_args = list_args + ['resultsdir=' + self._test.resultsdir]
        test_list = json.dumps([t.test() for t in tests])
        streamed_results = ''.join(
                [json.dumps(t.test_result()) + '\n'
                 for t in tests if t.start_time()])
        results_path = os.path.join(self._test.resultsdir,
                                    tast.tast._STREAMED_RESULTS_FILENAME)

        self._tast_commands = {
            'list': TastCommand(list_args, stdout=test_list),
            'run': TastCommand(run_args, file_path=results_path,
                               file_data=streamed_results),
        }

    def _run_test(self, ignore_test_failures=False):
        """Writes fake_tast.py's configuration and runs the test.

        @param ignore_test_failures: Passed as the identically-named arg to
            Tast.initialize().
        """
        self._test.initialize(FakeHost(self.HOST, self.PORT),
                              self.TEST_PATTERNS,
                              ignore_test_failures=ignore_test_failures,
                              max_run_sec=self.MAX_RUN_SEC,
                              install_root=self._root_dir)
        self._test.set_fake_now_for_testing(
                (NOW - tast._UNIX_EPOCH).total_seconds())

        cfg = {}
        for name, cmd in self._tast_commands.iteritems():
            cfg[name] = vars(cmd)
        path = os.path.join(os.path.dirname(self._tast_path), 'config.json')
        with open(path, 'a') as f:
            json.dump(cfg, f)

        try:
            self._test.run_once()
        finally:
            if self._job.post_run_hook:
                self._job.post_run_hook()

    def testPassingTests(self):
        """Tests that passing tests are reported correctly."""
        tests = [TestInfo('pkg.Test1', 0, 2),
                 TestInfo('pkg.Test2', 3, 5),
                 TestInfo('pkg.Test3', 6, 8)]
        self._init_tast_commands(tests)
        self._run_test()
        self.assertEqual(status_string(get_status_entries_from_tests(tests)),
                         status_string(self._job.status_entries))

    def testFailingTests(self):
        """Tests that failing tests are reported correctly."""
        tests = [TestInfo('pkg.Test1', 0, 2, errors=[('failed', 1)]),
                 TestInfo('pkg.Test2', 3, 6),
                 TestInfo('pkg.Test2', 7, 8, errors=[('another', 7)])]
        self._init_tast_commands(tests)
        with self.assertRaises(error.TestFail) as _:
            self._run_test()
        self.assertEqual(status_string(get_status_entries_from_tests(tests)),
                         status_string(self._job.status_entries))

    def testIgnoreTestFailures(self):
        """Tests that tast.tast can still pass with Tast test failures."""
        tests = [TestInfo('pkg.Test', 0, 2, errors=[('failed', 1)])]
        self._init_tast_commands(tests)
        self._run_test(ignore_test_failures=True)
        self.assertEqual(status_string(get_status_entries_from_tests(tests)),
                         status_string(self._job.status_entries))

    def testSkippedTest(self):
        """Tests that skipped tests aren't reported."""
        tests = [TestInfo('pkg.Normal', 0, 1),
                 TestInfo('pkg.Skipped', 2, 2, skip_reason='missing deps')]
        self._init_tast_commands(tests)
        self._run_test()
        self.assertEqual(status_string(get_status_entries_from_tests(tests)),
                         status_string(self._job.status_entries))

    def testSkippedTestWithErrors(self):
        """Tests that skipped tests are reported if they also report errors."""
        tests = [TestInfo('pkg.Normal', 0, 1),
                 TestInfo('pkg.SkippedWithErrors', 2, 2, skip_reason='bad deps',
                          errors=[('bad deps', 2)])]
        self._init_tast_commands(tests)
        with self.assertRaises(error.TestFail) as _:
            self._run_test()
        self.assertEqual(status_string(get_status_entries_from_tests(tests)),
                         status_string(self._job.status_entries))

    def testMissingTest(self):
        """Tests that a missing test is reported when there's another test."""
        tests = [TestInfo('pkg.Test1', 0, 2), TestInfo('pkg.Test2', None, None)]
        self._init_tast_commands(tests)
        self._run_test()
        self.assertEqual(status_string(get_status_entries_from_tests(tests)),
                         status_string(self._job.status_entries))

    def testNoTestsRun(self):
        """Tests that a missing test is reported when its the only test."""
        tests = [TestInfo('pkg.Test', None, None)]
        self._init_tast_commands(tests)
        self._run_test()
        self.assertEqual(status_string(get_status_entries_from_tests(tests)),
                         status_string(self._job.status_entries))

    def testHangingTest(self):
        """Tests that a not-finished test is reported."""
        tests = [TestInfo('pkg.Test1', 0, 2), TestInfo('pkg.Test2', 3, None)]
        self._init_tast_commands(tests)
        self._run_test()
        self.assertEqual(status_string(get_status_entries_from_tests(tests)),
                         status_string(self._job.status_entries))

    def testNoTestsMatched(self):
        """Tests that an error is raised if no tests are matched."""
        self._init_tast_commands([])
        with self.assertRaises(error.TestFail) as _:
            self._run_test()

    def testListCommandFails(self):
        """Tests that an error is raised if the list command fails."""
        self._init_tast_commands([])
        self._tast_commands['list'].status = 1
        with self.assertRaises(error.TestFail) as _:
            self._run_test()

    def testListCommandPrintsGarbage(self):
        """Tests that an error is raised if the list command prints bad data."""
        self._init_tast_commands([])
        self._tast_commands['list'].stdout = 'not valid JSON data'
        with self.assertRaises(error.TestFail) as _:
            self._run_test()

    def testRunCommandFails(self):
        """Tests that an error is raised if the run command fails."""
        tests = [TestInfo('pkg.Test1', 0, 1), TestInfo('pkg.Test2', 2, 3)]
        self._init_tast_commands(tests)
        self._tast_commands['run'].status = 1
        with self.assertRaises(error.TestFail) as _:
            self._run_test()
        self.assertEqual(status_string(get_status_entries_from_tests(tests)),
                         status_string(self._job.status_entries))

    def testRunCommandWritesTrailingGarbage(self):
        """Tests that an error is raised if the run command prints bad data."""
        tests = [TestInfo('pkg.Test1', 0, 1), TestInfo('pkg.Test2', None, None)]
        self._init_tast_commands(tests)
        self._tast_commands['run'].file_data += 'not valid JSON data'
        with self.assertRaises(error.TestFail) as _:
            self._run_test()
        self.assertEqual(status_string(get_status_entries_from_tests(tests)),
                         status_string(self._job.status_entries))

    def testNoResultsFile(self):
        """Tests that an error is raised if no results file is written."""
        tests = [TestInfo('pkg.Test1', None, None)]
        self._init_tast_commands(tests)
        self._tast_commands['run'].file_path = None
        with self.assertRaises(error.TestFail) as _:
            self._run_test()
        self.assertEqual(status_string(get_status_entries_from_tests(tests)),
                         status_string(self._job.status_entries))

    def testMissingTastExecutable(self):
        """Tests that an error is raised if the tast command isn't found."""
        os.remove(self._get_path_in_root(tast.tast._TAST_PATH))
        with self.assertRaises(error.TestFail) as _:
            self._run_test()

    def testMissingRemoteTestRunner(self):
        """Tests that an error is raised if remote_test_runner isn't found."""
        os.remove(self._get_path_in_root(tast.tast._REMOTE_TEST_RUNNER_PATH))
        with self.assertRaises(error.TestFail) as _:
            self._run_test()

    def testMissingRemoteBundleDir(self):
        """Tests that an error is raised if remote bundles aren't found."""
        shutil.rmtree(self._get_path_in_root(tast.tast._REMOTE_BUNDLE_DIR))
        with self.assertRaises(error.TestFail) as _:
            self._run_test()

    def testSspPaths(self):
        """Tests that files can be located at their alternate SSP locations."""
        for p in os.listdir(self._root_dir):
            shutil.rmtree(os.path.join(self._root_dir, p))
        self._set_up_root(ssp=True)

        tests = [TestInfo('pkg.Test', 0, 1)]
        self._init_tast_commands(tests)
        self._run_test()
        self.assertEqual(status_string(get_status_entries_from_tests(tests)),
                         status_string(self._job.status_entries))

    def testSumTestTimeouts(self):
        """Tests that test timeouts are summed for the overall timeout."""
        ns_in_sec = 1000000000
        tests = [TestInfo('pkg.Test1', 0, 0, timeout_ns=(23 * ns_in_sec)),
                 TestInfo('pkg.Test2', 0, 0, timeout_ns=(41 * ns_in_sec))]
        self._init_tast_commands(tests)
        self._run_test()
        self.assertEqual(64 + tast.tast._RUN_OVERHEAD_SEC,
                         self._test._get_run_tests_timeout_sec())

    def testCapTestTimeout(self):
        """Tests that excessive test timeouts are capped."""
        timeout_ns = 2 * self.MAX_RUN_SEC * 1000000000
        tests = [TestInfo('pkg.Test', 0, 0, timeout_ns=timeout_ns)]
        self._init_tast_commands(tests)
        self._run_test()
        self.assertEqual(self.MAX_RUN_SEC,
                         self._test._get_run_tests_timeout_sec())


class TestInfo:
    """Wraps information about a Tast test.

    This struct is used to:
    - get test definitions printed by fake_tast.py's 'list' command
    - get test results written by fake_tast.py's 'run' command
    - get expected base_job.status_log_entry objects that unit tests compare
      against what tast.Tast actually recorded
    """
    def __init__(self, name, start_offset, end_offset, errors=None,
                 skip_reason=None, attr=None, timeout_ns=0):
        """
        @param name: Name of the test, e.g. 'ui.ChromeLogin'.
        @param start_offset: Start time as int seconds offset from BASE_TIME,
            or None to indicate that tast didn't report a result for this test.
        @param end_offset: End time as int seconds offset from BASE_TIME, or
            None to indicate that tast reported that this test started but not
            that it finished.
        @param errors: List of (string, int) tuples containing reasons and
            seconds offsets of errors encountered while running the test, or
            None if no errors were encountered.
        @param skip_reason: Human-readable reason that the test was skipped, or
            None to indicate that it wasn't skipped.
        @param attr: List of string test attributes assigned to the test, or
            None if no attributes are assigned.
        @param timeout_ns: Test timeout in nanoseconds.
        """
        def from_offset(offset):
            """Returns an offset from BASE_TIME.

            @param offset: Offset as integer seconds.
            @return: datetime.datetime object.
            """
            if offset is None:
                return None
            return BASE_TIME + datetime.timedelta(0, offset)

        self._name = name
        self._start_time = from_offset(start_offset)
        self._end_time = from_offset(end_offset)
        self._errors = \
                [(e[0], from_offset(e[1])) for e in errors] if errors else []
        self._skip_reason = skip_reason
        self._attr = list(attr) if attr else []
        self._timeout_ns = timeout_ns

    def start_time(self):
        # pylint: disable=missing-docstring
        return self._start_time

    def test(self):
        """Returns a test dict printed by the 'list' command.

        @return: dict representing a Tast testing.Test struct.
        """
        return {
            'name': self._name,
            'attr': self._attr,
            'timeout': self._timeout_ns,
        }

    def test_result(self):
        """Returns a dict representing a result written by the 'run' command.

        @return: dict representing a Tast TestResult struct.
        """
        return {
            'name': self._name,
            'start': to_rfc3339(self._start_time),
            'end': to_rfc3339(self._end_time),
            'errors': [{'reason': e[0], 'time': to_rfc3339(e[1])}
                       for e in self._errors],
            'skipReason': self._skip_reason,
            'attr': self._attr,
            'timeout': self._timeout_ns,
        }

    def status_entries(self):
        """Returns expected base_job.status_log_entry objects for this test.

        @return: list of Autotest base_job.status_log_entry objects.
        """
        # Deliberately-skipped tests shouldn't have status entries unless errors
        # were also reported.
        if self._skip_reason and not self._errors:
            return []

        def make(status_code, dt, msg=''):
            """Makes a base_job.status_log_entry.

            @param status_code: String status code.
            @param dt: datetime.datetime object containing entry time.
            @param msg: String message (typically only set for errors).
            @return: base_job.status_log_entry object.
            """
            timestamp = int((dt - tast._UNIX_EPOCH).total_seconds())
            return base_job.status_log_entry(
                    status_code, None,
                    tast.tast._TEST_NAME_PREFIX + self._name, msg, None,
                    timestamp=timestamp)

        # Not-reported tests should use 'now' in status entries.
        entries = [make(tast.tast._JOB_STATUS_START, self._start_time or NOW)]

        if self._start_time and self._end_time and not self._errors:
            entries.append(make(tast.tast._JOB_STATUS_GOOD, self._end_time))
            entries.append(make(tast.tast._JOB_STATUS_END_GOOD, self._end_time))
        else:
            for e in self._errors:
                entries.append(make(tast.tast._JOB_STATUS_FAIL, e[1], e[0]))
            if not self._start_time:
                entries.append(make(tast.tast._JOB_STATUS_FAIL, NOW,
                                    tast.tast._TEST_NOT_RUN_MSG))
            elif not self._end_time:
                entries.append(make(tast.tast._JOB_STATUS_FAIL,
                                    self._start_time,
                                    tast.tast._TEST_DID_NOT_FINISH_MSG))
            entries.append(make(tast.tast._JOB_STATUS_END_FAIL,
                                self._end_time or self._start_time or NOW))

        return entries


class FakeServerJob:
    """Fake implementation of server_job from server/server_job.py."""
    def __init__(self, tmp_dir):
        self.pkgmgr = None
        self.autodir = None
        self.tmpdir = tmp_dir
        self.post_run_hook = None
        self.status_entries = []

    def add_post_run_hook(self, hook):
        """Stub implementation of server_job.add_post_run_hook."""
        self.post_run_hook = hook

    def record_entry(self, entry, log_in_subdir=True):
        """Stub implementation of server_job.record_entry."""
        assert(not log_in_subdir)
        self.status_entries.append(entry)


class FakeHost:
    """Fake implementation of AbstractSSHHost from server/hosts/abstract_ssh.py.
    """
    def __init__(self, hostname, port):
        self.hostname = hostname
        self.port = port


class TastCommand(object):
    """Args and behavior for fake_tast.py for a given command, e.g. "list"."""

    def __init__(self, required_args, status=0, stdout=None, stderr=None,
                 file_path=None, file_data=None):
        """
        @param required_args: List of required args, each specified as
            'name=value'. Names correspond to argparse-provided names in
            fake_tast.py (typically just the flag name, e.g. 'build' or
            'resultsdir'). Values correspond to str() representations of the
            argparse-provided values.
        @param status: Status code for fake_tast.py to return.
        @param stdout: Data to write to stdout.
        @param stderr: Data to write to stderr.
        @param file_path: File to create before exiting.
        @param file_data: Data to write to file_path.
        """
        self.required_args = required_args
        self.status = status
        self.stdout = stdout
        self.stderr = stderr
        self.file_path = file_path
        self.file_data = file_data


def to_rfc3339(t):
    """Returns an RFC3339 timestamp.

    @param t: UTC datetime.datetime object or None for the zero time.
    @return: String RFC3339 time, e.g. '2018-01-02T02:34:28Z'.
    """
    if t is None:
        return '0001-01-01T00:00:00Z'
    assert(not t.utcoffset())
    return t.strftime('%Y-%m-%dT%H:%M:%SZ')


def get_status_entries_from_tests(tests):
    """Returns a flattened list of status entries from TestInfo objects.

    @param tests: List of TestInfo objects.
    @return: Flattened list of base_job.status_log_entry objects produced by
        calling status_entries() on each TestInfo object.
    """
    return sum([t.status_entries() for t in tests], [])


def status_string(entries):
    """Returns a string describing a list of base_job.status_log_entry objects.

    @param entries: List of base_job.status_log_entry objects.
    @return: String containing space-separated representations of entries.
    """
    strings = []
    for entry in entries:
        timestamp = entry.fields[base_job.status_log_entry.TIMESTAMP_FIELD]
        s = '[%s %s %s %s]' % (timestamp, entry.operation, entry.status_code,
                               repr(str(entry.message)))
        strings.append(s)

    return ' '.join(strings)


if __name__ == '__main__':
    unittest.main()
