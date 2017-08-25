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
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.site_utils import lxc
from autotest_lib.site_utils.lxc import unittest_logging


options = None


class SharedHostDirTests(unittest.TestCase):
    """Unit tests for the ContainerBucket class."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.shared_host_path = os.path.join(self.tmpdir, 'host')


    def tearDown(self):
        shutil.rmtree(self.tmpdir)


    def testHostDirCreationAndCleanup(self):
        """Verifies that the host dir is properly created and cleaned up when
        the container bucket is set up and destroyed.
        """
        # Precondition: host path nonexistent
        self.assertFalse(os.path.isdir(self.shared_host_path))

        host_dir = lxc.SharedHostDir(self.shared_host_path)

        # Verify the host path in the host_dir.
        self.assertEqual(os.path.realpath(host_dir.path),
                         os.path.realpath(self.shared_host_path))
        self.assertTrue(os.path.isdir(self.shared_host_path))

        # Clean up, verify that the path is removed.
        host_dir.cleanup()
        self.assertFalse(os.path.isdir(self.shared_host_path))


    def testHostDirMissing(self):
        """Verifies that a missing host dir does not cause cleanup to crash.
        """
        host_dir = lxc.SharedHostDir(self.shared_host_path)

        # Manually destroy the host path
        utils.run('sudo umount %(path)s && sudo rmdir %(path)s' %
                  {'path': self.shared_host_path})

        # Verify that the host path does not exist.
        self.assertFalse(os.path.exists(self.shared_host_path))
        try:
            host_dir.cleanup()
        except:
            self.fail('SharedHostDir.cleanup crashed.\n%s' %
                      error.format_error())


    def testHostDirNotMounted(self):
        """Verifies that an unmounted host dir does not cause container bucket
        construction to crash.
        """
        # Create the shared host dir, but do not mount it.
        os.makedirs(self.shared_host_path)

        # Setup then destroy the HPM.  This should not emit any exceptions.
        try:
            host_dir = lxc.SharedHostDir(self.shared_host_path)
            host_dir.cleanup()
        except:
            self.fail('SharedHostDir crashed.\n%s' % error.format_error())


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
