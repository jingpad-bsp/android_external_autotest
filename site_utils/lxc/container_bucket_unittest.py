#!/usr/bin/python
# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import logging
import os
import shutil
import tempfile
import unittest

import common
from autotest_lib.site_utils import lxc
from autotest_lib.site_utils.lxc import unittest_logging


options = None
container_path = None

def setUpModule():
    """Creates a directory for running the unit tests. """
    global container_path
    container_path = tempfile.mkdtemp(
            dir=lxc.DEFAULT_CONTAINER_PATH,
            prefix='container_bucket_unittest_')


def tearDownModule():
    """Deletes the test directory. """
    shutil.rmtree(container_path)


class ContainerBucketTests(unittest.TestCase):
    """Unit tests for the ContainerBucket class."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.shared_host_path = os.path.realpath(os.path.join(self.tmpdir,
                                                              'host'))


    def tearDown(self):
        shutil.rmtree(self.tmpdir)


    def testHostDirCreationAndCleanup(self):
        """Verifies that the host dir is properly created and cleaned up when
        the container bucket is set up and destroyed.
        """
        bucket = lxc.ContainerBucket(container_path, self.shared_host_path)

        # Verify the host path in the container bucket.
        self.assertEqual(os.path.realpath(bucket.shared_host_path),
                         self.shared_host_path)

        # Set up, verify that the path is created.
        bucket.setup_shared_host_path()
        self.assertTrue(os.path.isdir(self.shared_host_path))

        # Clean up, verify that the path is removed.
        bucket.destroy_all()
        self.assertFalse(os.path.isdir(self.shared_host_path))


    def testHostDirMissing(self):
        """Verifies that a missing host dir does not cause container bucket
        destruction to crash.
        """
        bucket = lxc.ContainerBucket(container_path, self.shared_host_path)

        # Verify that the host path does not exist.
        self.assertFalse(os.path.exists(self.shared_host_path))
        # Do not call startup, just call destroy.  This should not throw.
        bucket.destroy_all()


    def testHostDirNotMounted(self):
        """Verifies that an unmounted host dir does not cause container bucket
        construction to crash.
        """
        # Create the shared host dir, but do not mount it.
        os.makedirs(self.shared_host_path)
        bucket = lxc.ContainerBucket(container_path, self.shared_host_path)

        # Setup then destroy the bucket.  This should not emit any exceptions.
        bucket.setup_shared_host_path()
        bucket.destroy_all()


def parse_options():
    """Parse command line inputs."""
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Print out ALL entries.')
    args, _unused = parser.parse_known_args()
    return args


if __name__ == '__main__':
    options = parse_options()

    log_level=(logging.DEBUG if options.verbose else logging.INFO)
    unittest_logging.setup(log_level)

    unittest.main()
