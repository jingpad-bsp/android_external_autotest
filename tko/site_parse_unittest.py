#!/usr/bin/python -u
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#

import glob, os, shutil, tempfile, time, unittest

import common
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.tko.site_parse import StackTrace


class stack_trace_test(unittest.TestCase):


    def setUp(self):
        self._fake_results = tempfile.mkdtemp()
        self._cros_src_dir = global_config.global_config.get_config_value(
            'CROS', 'source_tree', default=None)

        if not self._cros_src_dir:
            self.fail('No Chrome OS source tree defined in global_config.ini')

        self._stack_trace = StackTrace(
            self._fake_results, self._cros_src_dir)

        self._cache_dir = os.path.join(
            self._cros_src_dir, 'chroot', self._stack_trace._CACHE_DIR)

        # Ensure we don't obliterate a live cache directory by accident.
        if os.path.exists(self._cache_dir):
            self.fail(
                'Symbol cache directory already exists. Cowardly refusing to'
                ' run. Please remove this directory manually to continue.')


    def tearDown(self):
        shutil.rmtree(self._fake_results)
        if os.path.exists(self._cache_dir):
            shutil.rmtree(self._cache_dir)


    def _setup_basic_cache(self,
                           job_name='x86-alex-r16-R16-1166.0.0-a1-b1118_bvt',
                           mkdir=True):
        # Ensure cache directory is present.
        self._stack_trace._get_cache_dir()
        board, rev, version = self._stack_trace._parse_job_name(job_name)

        symbols_dir = os.path.join(
            self._cache_dir, '-'.join([board, rev, version]))
        if mkdir:
            os.mkdir(symbols_dir)

        chroot_symbols_dir = os.sep + os.path.relpath(
            symbols_dir, self._stack_trace._chroot_dir)

        return job_name, symbols_dir, chroot_symbols_dir


    def test_get_job_name(self):
        job_name = 'x86-alex-r16-R16-1166.0.0-a1-b1118_regression'
        with open(os.path.join(self._fake_results, 'keyval'), 'w') as f:
            f.write('label=%s' % job_name)

        self.assertEqual(self._stack_trace._get_job_name(), job_name)


    def test_parse_3_tuple_job_name(self):
        job_name = 'x86-alex-r16-R16-1166.0.0-a1-b1118_regression'
        board, rev, version = self._stack_trace._parse_job_name(job_name)
        self.assertEqual(board, 'x86-alex')
        self.assertEqual(rev, 'r16')
        self.assertEqual(version, '1166.0.0')


    def test_parse_4_tuple_job_name(self):
        job_name = 'x86-mario-r15-0.15.1011.74-a1-b61_bvt'
        board, rev, version = self._stack_trace._parse_job_name(job_name)
        self.assertEqual(board, 'x86-mario')
        self.assertEqual(rev, 'r15')
        self.assertEqual(version, '0.15.1011.74')


    def test_parse_4_tuple_au_job_name(self):
        job_name = 'x86-alex-r15-0.15.1011.81_to_0.15.1011.82-a1-b69_mton_au'
        board, rev, version = self._stack_trace._parse_job_name(job_name)
        self.assertEqual(board, 'x86-alex')
        self.assertEqual(rev, 'r15')
        self.assertEqual(version, '0.15.1011.82')


    def test_parse_3_tuple_au_job_name(self):
        job_name = 'x86-alex-r16-1165.0.0_to_R16-1166.0.0-a1-b69_mton_au'
        board, rev, version = self._stack_trace._parse_job_name(job_name)
        self.assertEqual(board, 'x86-alex')
        self.assertEqual(rev, 'r16')
        self.assertEqual(version, '1166.0.0')


    def test_get_cache_dir(self):
        # Test without existing cache dir.
        self.assertFalse(os.path.exists(self._cache_dir))
        self.assertEquals(self._stack_trace._get_cache_dir(), self._cache_dir)
        self.assertTrue(os.path.exists(self._cache_dir))

        # Test with existing cache dir.
        self.assertEquals(self._stack_trace._get_cache_dir(), self._cache_dir)


    def test_get_symbol_dir_with_cache(self):
        job_name, symbols_dir, chroot_symbols_dir = self._setup_basic_cache()

        # Create completed file.
        open(os.path.join(
            symbols_dir, self._stack_trace._COMPLETE_FILE), 'w').close()
        self.assertEqual(
            self._stack_trace._get_symbol_dir(job_name), chroot_symbols_dir)


    def test_get_symbol_dir_with_incomplete_cache(self):
        # Create symbol dir w/o completed file.
        job_name, symbols_dir, chroot_symbols_dir = self._setup_basic_cache()

        self.god = mock.mock_god()
        self.god.stub_function(utils, 'poll_for_condition')
        utils.poll_for_condition.expect_any_call()

        self.assertEqual(
            self._stack_trace._get_symbol_dir(job_name), chroot_symbols_dir)

        self.god.unstub_all()


    def test_get_symbol_dir_with_incomplete_cache_timeout(self):
        # Create symbol dir w/o completed file.
        job_name, symbols_dir, chroot_symbols_dir = self._setup_basic_cache()

        # Adjust timeout to be very low. Ensure exception is raised.
        self._stack_trace._SYMBOL_WAIT_TIMEOUT = 1
        self.assertRaises(
            utils.TimeoutError, self._stack_trace._get_symbol_dir, job_name)


    def test_trim_cache(self):
        # Ensure cache dir is created.
        self._stack_trace._get_cache_dir()

        # Create 4 folders, 2 >24hrs old, 2 recent.
        dirs = [
            ('oldest', time.time() - 60*60*24*10),
            ('old', time.time() - 60*60*24),
            ('new', time.time() - 60*60*12),
            ('newest', time.time())]

        for dname, dtime in dirs:
            dpath = os.path.join(self._cache_dir, dname)
            os.mkdir(dpath)
            os.utime(dpath, (dtime, dtime))

        self._stack_trace._trim_cache()

        # Ensure only folders < 24hrs old exist.
        for dname, dtime in dirs:
            dpath = os.path.join(self._cache_dir, dname)
            self.assertEquals(
                os.path.exists(dpath), time.time() - dtime < 60*60*24)


    def test_setup_cleanup_results_in_chroot(self):
        # Write junk file to results directory.
        test_string = 'junkity junk junk junk.'
        junk_results_file = os.path.join(self._fake_results, 'junk.txt')
        with open(junk_results_file, 'w') as f:
            f.write(test_string)

        # Mount results directory inside of chroot.
        chroot_results_dir = self._stack_trace._setup_results_in_chroot()

        full_chroot_results_dir = os.path.join(
            self._stack_trace._chroot_dir, chroot_results_dir.lstrip(os.sep))

        # Ensure results directory is mounted into chroot w/ r,w privs.
        test_string_2 = 'with a dash of salt and pepper.'
        junk_chroot_file = os.path.join(full_chroot_results_dir, 'junk.txt')
        with open(junk_chroot_file, 'a+') as f:
            self.assertEquals(test_string, f.read())
            f.write(test_string_2)

        # Unmount results directory and ensure mount pt is cleaned up.
        self._stack_trace._cleanup_results_in_chroot(chroot_results_dir)
        self.assertFalse(os.path.exists(full_chroot_results_dir))

        # Ensure data we wrote is still there.
        with open(junk_results_file, 'r') as f:
            self.assertEqual(test_string + test_string_2, f.read())


    def test_generate_stack_traces_with_live_data(self):
        # Retrieve cores from results set with known crashes. Corresponds to
        # beta build x86-alex-r15-0.15.1011.73-a1-b60. gsutil doesn't properly
        # rebuild directory structure on download, so just grab the cores.
        utils.run(
            'gsutil -m cp'
            ' gs://chromeos-autotest-results/68803-chromeos-test/*.dmp'
            ' %s' % self._fake_results)

        # Grab keyval file
        utils.run(
            'gsutil -m cp'
            ' gs://chromeos-autotest-results/68803-chromeos-test/group0/keyval'
            ' %s' % self._fake_results)

        # Enumerate existing .dmp files.
        cores = glob.glob('%s/*.dmp' % self._fake_results)

        # Generate stack traces...
        self._stack_trace.generate()

        # Ensure each core has a .dmp.txt file.
        for core in cores:
            self.assertTrue(os.path.exists(core + '.txt'))

        # Check the cache to make sure it was properly setup.
        job_name = self._stack_trace._get_job_name()
        _, symbols_dir, chroot_symbols_dir = self._setup_basic_cache(
            job_name=job_name, mkdir=False)
        self.assertEqual(
            self._stack_trace._get_symbol_dir(job_name), chroot_symbols_dir)
        self.assertTrue(os.path.exists(os.path.join(
            symbols_dir, self._stack_trace._COMPLETE_FILE)))


if __name__ == "__main__":
    unittest.main()
