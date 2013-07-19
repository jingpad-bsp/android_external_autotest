#!/usr/bin/python
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
# pylint: disable-msg=C0111

import os, unittest
import mox
import common
import subprocess
import stat
import tempfile
from autotest_lib.site_utils import test_that


class StartsWithList(mox.Comparator):
    def __init__(self, start_of_list):
        """Mox comparator which returns True if the argument
        to the mocked function is a list that begins with the elements
        in start_of_list.
        """
        self._lhs = start_of_list

    def equals(self, rhs):
        if len(rhs)<len(self._lhs):
            return False
        for (x,y) in zip(self._lhs, rhs):
            if x != y:
                return False
        return True


class ContainsSublist(mox.Comparator):
    def __init__(self, sublist):
        """Mox comparator which returns True if the argument
        to the mocked function is a list that contains sublist
        as a sub-list.
        """
        self._sublist = sublist

    def equals(self, rhs):
        n = len(self._sublist)
        if len(rhs)<n:
            return False
        return any((self._sublist == rhs[i:i+n])
                   for i in xrange(len(rhs) - n + 1))


class TestThatUnittests(unittest.TestCase):
    def test_validate_arguments(self):
        # Deferred until validate_arguments allows for lab runs.
        pass

    def test_parse_arguments(self):
        args = test_that.parse_arguments(
                ['-b', 'some_board', '-i', 'some_image', '--args', 'some_args',
                 'some_remote', 'test1', 'test2'])
        self.assertEqual('some_board', args.board)
        self.assertEqual('some_image', args.build)
        self.assertEqual('some_args', args.args)
        self.assertEqual('some_remote', args.remote)
        self.assertEqual(['test1', 'test2'], args.tests)

    def test_schedule_local_suite(self):
        # Deferred until schedule_local_suite knows about non-local builds.
        pass

    def test_schedule_local_test(self):
        # Deferred until schedule_local_test knows about non-local builds.
        pass

    def test_run_job(self):
        class Object():
            pass

        autotest_path = 'htap_tsetotua'
        autoserv_command = os.path.join(autotest_path, 'server', 'autoserv')
        remote = 'etomer'
        results_dir = '/tmp/fakeresults'
        fast_mode = False
        job1_results_dir = '/tmp/fakeresults/results-1'
        job2_results_dir = '/tmp/fakeresults/results-2'
        args = 'matey'
        expected_args_sublist = ['--args', args]
        self.mox = mox.Mox()

        # Create some dummy job objects.
        job1 = Object()
        job2 = Object()
        setattr(job1, 'control_type', 'cLiEnT')
        setattr(job1, 'control_file', 'c1')
        setattr(job1, 'id', 1)
        setattr(job2, 'control_type', 'Server')
        setattr(job2, 'control_file', 'c2')
        setattr(job2, 'id', 2)

        id_digits = 1

        # Stub out subprocess.Popen and wait calls.
        # Make them expect correct arguments.
        mock_process_1 = self.mox.CreateMock(subprocess.Popen)
        mock_process_2 = self.mox.CreateMock(subprocess.Popen)
        self.mox.StubOutWithMock(subprocess, 'Popen')

        arglist_1 = [autoserv_command, '-p', '-r', job1_results_dir, '-m',
                     remote, '-c']
        subprocess.Popen(mox.And(StartsWithList(arglist_1),
                                 ContainsSublist(expected_args_sublist))
                        ).AndReturn(mock_process_1)
        mock_process_1.wait()

        arglist_2 = [autoserv_command, '-p', '-r', job2_results_dir, '-m',
                     remote, '-s']
        subprocess.Popen(mox.And(StartsWithList(arglist_2),
                                 ContainsSublist(expected_args_sublist))
                        ).AndReturn(mock_process_2)
        mock_process_2.wait()

        # Test run_job.
        self.mox.ReplayAll()
        job_res = test_that.run_job(job1, remote, autotest_path, results_dir,
                                    fast_mode, id_digits, args)
        self.assertEqual(job_res, job1_results_dir)
        job_res = test_that.run_job(job2, remote, autotest_path, results_dir,
                                    fast_mode, id_digits, args)

        self.assertEqual(job_res, job2_results_dir)
        self.mox.UnsetStubs()
        self.mox.VerifyAll()
        self.mox.ResetAll()


    def test_perform_local_run(self):
        afe = test_that.setup_local_afe()
        autotest_path = 'ottotest_path'
        suite_name = 'sweet_name'
        remote = 'remoat'
        build = 'bild'
        board = 'bored'
        fast_mode = False
        suite_control_files=['c1', 'c2', 'c3', 'c4']
        results_dir = '/tmp/test_that_results_fake'
        id_digits = 1
        args = 'matey'

        def fake_suite_callback(*args, **dargs):
            for control_file in suite_control_files:
                afe.create_job(control_file, hosts=[remote])

        # Mock out scheduling of suite and running of jobs.
        self.mox = mox.Mox()
        self.mox.StubOutWithMock(test_that, 'schedule_local_suite')
        test_that.schedule_local_suite(autotest_path, suite_name,
                afe, build=build,
                board=board, results_directory=results_dir
                ).WithSideEffects(fake_suite_callback)
        self.mox.StubOutWithMock(test_that, 'run_job')

        # Mock out temporary results directory creation
        self.mox.StubOutWithMock(tempfile, 'mkdtemp')
        self.mox.StubOutWithMock(os, 'chmod')
        tempfile.mkdtemp(prefix='test_that_results_').AndReturn(results_dir)
        os.chmod(results_dir, stat.S_IWOTH | stat.S_IROTH | stat.S_IXOTH)

        # Test perform_local_run. Enforce that run_job is called correctly.
        for control_file in suite_control_files:
            test_that.run_job(mox.ContainsAttributeValue('control_file',
                                                         control_file),
                             remote, autotest_path, results_dir, fast_mode,
                             id_digits, args, False)
        self.mox.ReplayAll()
        test_that.perform_local_run(afe, autotest_path, ['suite:'+suite_name],
                                    remote, fast_mode, build=build, board=board,
                                    args=args)
        self.mox.UnsetStubs()
        self.mox.VerifyAll()


if __name__ == '__main__':
    unittest.main()
