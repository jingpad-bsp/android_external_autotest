"""Tests for job_directories."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import contextlib
import os
import shutil
import tempfile
import unittest

import common
from autotest_lib.site_utils import job_directories


class SwarmingJobDirectoryTestCase(unittest.TestCase):
    """Tests SwarmingJobDirectory."""

    def test_get_job_directories_legacy(self):
        with _change_to_tempdir():
            os.makedirs("swarming-3e4391423c3a4311/b")
            os.mkdir("not-a-swarming-dir")
            results = job_directories.SwarmingJobDirectory.get_job_directories()
            self.assertEqual(set(results), {"swarming-3e4391423c3a4311"})

    def test_get_job_directories(self):
        with _change_to_tempdir():
            os.makedirs("swarming-3e4391423c3a4310/1")
            os.makedirs("swarming-3e4391423c3a4310/0")
            os.makedirs("swarming-3e4391423c3a4310/a")
            os.mkdir("not-a-swarming-dir")
            results = job_directories.SwarmingJobDirectory.get_job_directories()
            self.assertEqual(set(results),
                             {"swarming-3e4391423c3a4310/1",
                              "swarming-3e4391423c3a4310/a"})


class GetJobIDOrTaskID(unittest.TestCase):
    """Tests get_job_id_or_task_id."""

    def test_legacy_swarming_path(self):
        self.assertEqual(
                "3e4391423c3a4311",
                job_directories.get_job_id_or_task_id(
                        "/autotest/results/swarming-3e4391423c3a4311"),
        )
        self.assertEqual(
                "3e4391423c3a4311",
                job_directories.get_job_id_or_task_id(
                        "swarming-3e4391423c3a4311"),
        )

    def test_swarming_path(self):
        self.assertEqual(
                "3e4391423c3a4311",
                job_directories.get_job_id_or_task_id(
                        "/autotest/results/swarming-3e4391423c3a4310/1"),
        )
        self.assertEqual(
                "3e4391423c3a431f",
                job_directories.get_job_id_or_task_id(
                        "swarming-3e4391423c3a4310/f"),
        )



@contextlib.contextmanager
def _change_to_tempdir():
    old_dir = os.getcwd()
    tempdir = tempfile.mkdtemp('job_directories_unittest')
    try:
        os.chdir(tempdir)
        yield
    finally:
        os.chdir(old_dir)
        shutil.rmtree(tempdir)

if __name__ == '__main__':
    unittest.main()
