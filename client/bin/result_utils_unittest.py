#!/usr/bin/python
# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""unittest for result_utils.py
"""

import os
import shutil
import tempfile
import unittest

import common
from autotest_lib.client.bin import result_utils


SIZE = 10
EXPECTED_SUMMARY = {
        '': {result_utils.TOTAL_SIZE_BYTES: 4 * SIZE,
             result_utils.DIRS: {
                     'file1': {result_utils.TOTAL_SIZE_BYTES: SIZE},
                     'folder1': {result_utils.TOTAL_SIZE_BYTES: 2 * SIZE,
                                 result_utils.DIRS: {
                                  'file2': {
                                      result_utils.TOTAL_SIZE_BYTES: SIZE},
                                  'file3': {
                                      result_utils.TOTAL_SIZE_BYTES: SIZE},
                                  'symlink': {result_utils.TOTAL_SIZE_BYTES: 0,
                                              result_utils.DIRS: {}}}},
                     'folder2': {result_utils.TOTAL_SIZE_BYTES: SIZE,
                                 result_utils.DIRS:
                                     {'file2': {result_utils.TOTAL_SIZE_BYTES:
                                                SIZE}},
                                }}}}

class GetDirSummaryTest(unittest.TestCase):
    """Test class for get_dir_summary method"""

    def create_file(self, path):
        """Create a temp file at given path with the given size.

        @param path: Path to the temp file.
        @param size: Size of the temp file, default to SIZE.
        """
        with open(path, 'w') as f:
            f.write('A' * SIZE)


    def setUp(self):
        """Setup directory for test."""
        self.test_dir = tempfile.mkdtemp()
        file1 = os.path.join(self.test_dir, 'file1')
        self.create_file(file1)
        folder1 = os.path.join(self.test_dir, 'folder1')
        os.mkdir(folder1)
        file2 = os.path.join(folder1, 'file2')
        self.create_file(file2)
        file3 = os.path.join(folder1, 'file3')
        self.create_file(file3)

        folder2 = os.path.join(self.test_dir, 'folder2')
        os.mkdir(folder2)
        file4 = os.path.join(folder2, 'file2')
        self.create_file(file4)

        symlink = os.path.join(folder1, 'symlink')
        os.symlink(folder2, symlink)


    def tearDown(self):
        """Cleanup the test directory."""
        shutil.rmtree(self.test_dir, ignore_errors=True)


    def test_get_dir_summary(self):
        """Test method get_dir_summary."""
        summary_json = result_utils.get_dir_summary(
                self.test_dir + '/', self.test_dir + '/')
        self.assertEqual(EXPECTED_SUMMARY, summary_json)


# this is so the test can be run in standalone mode
if __name__ == '__main__':
    """Main"""
    unittest.main()
