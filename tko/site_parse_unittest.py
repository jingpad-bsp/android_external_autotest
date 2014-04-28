#!/usr/bin/python -u
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#

#pylint: disable-msg=C0111

import os, shutil, tempfile, unittest

import common
from autotest_lib.client.common_lib import global_config
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


if __name__ == "__main__":
    unittest.main()
