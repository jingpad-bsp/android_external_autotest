#!/usr/bin/python
# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""unittest for result_utils.py
"""

import json
import os
import shutil
import tempfile
import time
import unittest

import common
from autotest_lib.client.bin import result_utils


SIZE = 10
EXPECTED_SUMMARY = {
        '': {result_utils.ORIGINAL_SIZE_BYTES: 4 * SIZE,
             result_utils.DIRS: {
                     'file1': {result_utils.ORIGINAL_SIZE_BYTES: SIZE},
                     'folder1': {result_utils.ORIGINAL_SIZE_BYTES: 2 * SIZE,
                                 result_utils.DIRS: {
                                  'file2': {
                                      result_utils.ORIGINAL_SIZE_BYTES: SIZE},
                                  'file3': {
                                      result_utils.ORIGINAL_SIZE_BYTES: SIZE},
                                  'symlink': {
                                      result_utils.ORIGINAL_SIZE_BYTES: 0,
                                      result_utils.DIRS: {}}}},
                     'folder2': {result_utils.ORIGINAL_SIZE_BYTES: SIZE,
                                 result_utils.DIRS:
                                     {'file2':
                                        {result_utils.ORIGINAL_SIZE_BYTES:
                                         SIZE}},
                                }}}}

SUMMARY_1 = {
  '': {result_utils.ORIGINAL_SIZE_BYTES: 4 * SIZE,
       result_utils.DIRS: {
         'file1': {result_utils.ORIGINAL_SIZE_BYTES: SIZE},
         'file2': {result_utils.ORIGINAL_SIZE_BYTES: SIZE},
         'folder_not_overwritten':
            {result_utils.ORIGINAL_SIZE_BYTES: SIZE,
             result_utils.DIRS: {
               'file1': {result_utils.ORIGINAL_SIZE_BYTES: SIZE}}
            },
          'file_to_be_overwritten': {result_utils.ORIGINAL_SIZE_BYTES: SIZE},
        }
      }
  }

SUMMARY_2 = {
  '': {result_utils.ORIGINAL_SIZE_BYTES: 26 * SIZE,
       result_utils.DIRS: {
         # `file1` exists and has the same size.
         'file1': {result_utils.ORIGINAL_SIZE_BYTES: SIZE},
         # Change the size of `file2` to make sure summary merge works.
         'file2': {result_utils.ORIGINAL_SIZE_BYTES: 2 * SIZE},
         # `file3` is new.
         'file3': {result_utils.ORIGINAL_SIZE_BYTES: SIZE},
         # Add a new sub-directory.
         'folder1': {result_utils.ORIGINAL_SIZE_BYTES: 20 * SIZE,
                     result_utils.TRIMMED_SIZE_BYTES: SIZE,
                     result_utils.DIRS: {
                         # Add a file being trimmed.
                         'file4': {
                           result_utils.ORIGINAL_SIZE_BYTES: 20 * SIZE,
                           result_utils.TRIMMED_SIZE_BYTES: SIZE}
                         }
                     },
          # Add a file whose name collides with the previous summary.
          'folder_not_overwritten': {
            result_utils.ORIGINAL_SIZE_BYTES: 100 * SIZE},
          # Add a directory whose name collides with the previous summary.
          'file_to_be_overwritten':
            {result_utils.ORIGINAL_SIZE_BYTES: SIZE,
             result_utils.DIRS: {
               'file1': {result_utils.ORIGINAL_SIZE_BYTES: SIZE}}
            },
          # Folder was collected, not missing from the final result folder.
          'folder_tobe_deleted':
            {result_utils.ORIGINAL_SIZE_BYTES: SIZE,
             result_utils.DIRS: {
               'file_tobe_deleted': {result_utils.ORIGINAL_SIZE_BYTES: SIZE}}
            },
        }
      }
  }

SUMMARY_1_SIZE = 171
SUMMARY_2_SIZE = 345

# The final result dir has an extra folder and file, also with `file3` removed
# to test the case that client files are removed on the server side.
EXPECTED_MERGED_SUMMARY = {
  '': {result_utils.ORIGINAL_SIZE_BYTES:
           37 * SIZE + SUMMARY_1_SIZE + SUMMARY_2_SIZE,
       result_utils.TRIMMED_SIZE_BYTES:
           17 * SIZE + SUMMARY_1_SIZE + SUMMARY_2_SIZE,
       # Size collected is SIZE bytes more than total size as an old `file2` of
       # SIZE bytes is overwritten by a newer file.
       result_utils.COLLECTED_SIZE_BYTES:
           19 * SIZE + SUMMARY_1_SIZE + SUMMARY_2_SIZE,
       result_utils.DIRS: {
         'dir_summary_1.json': {
           result_utils.ORIGINAL_SIZE_BYTES: SUMMARY_1_SIZE},
         'dir_summary_2.json': {
           result_utils.ORIGINAL_SIZE_BYTES: SUMMARY_2_SIZE},
         'file1': {result_utils.ORIGINAL_SIZE_BYTES: SIZE},
         'file2': {result_utils.ORIGINAL_SIZE_BYTES: 2 * SIZE,
                   result_utils.COLLECTED_SIZE_BYTES: 3 * SIZE,
                   result_utils.TRIMMED_SIZE_BYTES: 2 * SIZE},
         'file3': {result_utils.ORIGINAL_SIZE_BYTES: SIZE},
         'folder1': {result_utils.ORIGINAL_SIZE_BYTES: 20 * SIZE,
                     result_utils.TRIMMED_SIZE_BYTES: SIZE,
                     result_utils.COLLECTED_SIZE_BYTES: SIZE,
                     result_utils.DIRS: {
                         'file4': {result_utils.ORIGINAL_SIZE_BYTES: 20 * SIZE,
                                   result_utils.TRIMMED_SIZE_BYTES: SIZE}
                         }
                     },
         'folder2': {result_utils.ORIGINAL_SIZE_BYTES: 10 * SIZE,
                     result_utils.COLLECTED_SIZE_BYTES: 10 * SIZE,
                     result_utils.TRIMMED_SIZE_BYTES: 10 * SIZE,
                     result_utils.DIRS: {
                         'server_file': {
                           result_utils.ORIGINAL_SIZE_BYTES: 10 * SIZE}
                         }
                     },
         'folder_not_overwritten':
            {result_utils.ORIGINAL_SIZE_BYTES: SIZE,
             result_utils.COLLECTED_SIZE_BYTES: SIZE,
             result_utils.TRIMMED_SIZE_BYTES: SIZE,
             result_utils.DIRS: {
               'file1': {result_utils.ORIGINAL_SIZE_BYTES: SIZE}}
            },
         'file_to_be_overwritten':
           {result_utils.ORIGINAL_SIZE_BYTES: SIZE,
            result_utils.COLLECTED_SIZE_BYTES: SIZE,
            result_utils.TRIMMED_SIZE_BYTES: SIZE,
            result_utils.DIRS: {
              'file1': {result_utils.ORIGINAL_SIZE_BYTES: SIZE}}
           },
         'folder_tobe_deleted':
           {result_utils.ORIGINAL_SIZE_BYTES: SIZE,
            result_utils.COLLECTED_SIZE_BYTES: SIZE,
            result_utils.TRIMMED_SIZE_BYTES: 0,
            result_utils.DIRS: {
              'file_tobe_deleted': {result_utils.ORIGINAL_SIZE_BYTES: SIZE,
                                    result_utils.COLLECTED_SIZE_BYTES: SIZE,
                                    result_utils.TRIMMED_SIZE_BYTES: 0}}
           },
        }
      }
  }

def create_file(path, size=SIZE):
    """Create a temp file at given path with the given size.

    @param path: Path to the temp file.
    @param size: Size of the temp file, default to SIZE.
    """
    with open(path, 'w') as f:
        f.write('A' * size)


class GetDirSummaryTest(unittest.TestCase):
    """Test class for get_dir_summary method"""

    def setUp(self):
        """Setup directory for test."""
        self.test_dir = tempfile.mkdtemp()
        file1 = os.path.join(self.test_dir, 'file1')
        create_file(file1)
        folder1 = os.path.join(self.test_dir, 'folder1')
        os.mkdir(folder1)
        file2 = os.path.join(folder1, 'file2')
        create_file(file2)
        file3 = os.path.join(folder1, 'file3')
        create_file(file3)

        folder2 = os.path.join(self.test_dir, 'folder2')
        os.mkdir(folder2)
        file4 = os.path.join(folder2, 'file2')
        create_file(file4)

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


class MergeSummaryTest(unittest.TestCase):
    """Test class for merge_summaries method"""

    def setUp(self):
        """Setup directory to match the file structure in MERGED_SUMMARY."""
        self.test_dir = tempfile.mkdtemp() + '/'
        file1 = os.path.join(self.test_dir, 'file1')
        create_file(file1)
        file2 = os.path.join(self.test_dir, 'file2')
        create_file(file2, 2*SIZE)
        file3 = os.path.join(self.test_dir, 'file3')
        create_file(file3, SIZE)
        folder1 = os.path.join(self.test_dir, 'folder1')
        os.mkdir(folder1)
        file4 = os.path.join(folder1, 'file4')
        create_file(file4, SIZE)
        folder2 = os.path.join(self.test_dir, 'folder2')
        os.mkdir(folder2)
        server_file = os.path.join(folder2, 'server_file')
        create_file(server_file, 10*SIZE)
        folder_not_overwritten = os.path.join(
                self.test_dir, 'folder_not_overwritten')
        os.mkdir(folder_not_overwritten)
        file1 = os.path.join(folder_not_overwritten, 'file1')
        create_file(file1)
        file_to_be_overwritten = os.path.join(
                self.test_dir, 'file_to_be_overwritten')
        os.mkdir(file_to_be_overwritten)
        file1 = os.path.join(file_to_be_overwritten, 'file1')
        create_file(file1)

        # Save summary file to test_dir
        self.summary_1 = os.path.join(self.test_dir, 'dir_summary_1.json')
        with open(self.summary_1, 'w') as f:
            json.dump(SUMMARY_1, f)
        # Wait for 10ms, to make sure summary_2 has a later time stamp.
        time.sleep(0.01)
        self.summary_2 = os.path.join(self.test_dir, 'dir_summary_2.json')
        with open(self.summary_2, 'w') as f:
            json.dump(SUMMARY_2, f)

    def tearDown(self):
        """Cleanup the test directory."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def testMergeSummaries(self):
        """Test method merge_summaries."""
        client_collected_bytes, merged_summary = result_utils.merge_summaries(
                self.test_dir)
        self.assertEqual(EXPECTED_MERGED_SUMMARY, merged_summary)
        self.assertEqual(client_collected_bytes, 9 * SIZE)

    def testMergeSummariesFromNoHistory(self):
        """Test method merge_summaries can handle results with no existing
        summary.
        """
        os.remove(self.summary_1)
        os.remove(self.summary_2)
        client_collected_bytes, _ = result_utils.merge_summaries(self.test_dir)
        self.assertEqual(client_collected_bytes, 0)


# this is so the test can be run in standalone mode
if __name__ == '__main__':
    """Main"""
    unittest.main()
