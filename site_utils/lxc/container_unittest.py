#!/usr/bin/python
# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import logging
import os
import tempfile
import shutil
import sys
import unittest

import common
from autotest_lib.client.common_lib import error
from autotest_lib.site_utils import lxc
from autotest_lib.site_utils.lxc import unittest_logging
from autotest_lib.site_utils.lxc import utils as lxc_utils


options = None

class ContainerTests(unittest.TestCase):
    """Unit tests for the Container class."""

    @classmethod
    def setUpClass(cls):
        logging.debug('setupclass')
        cls.test_dir = tempfile.mkdtemp(dir=lxc.DEFAULT_CONTAINER_PATH,
                                        prefix='container_unittest_')
        cls.shared_host_path = os.path.join(cls.test_dir, 'host')

        # Use a container bucket just to download and set up the base image.
        cls.bucket = lxc.ContainerBucket(cls.test_dir, cls.shared_host_path)

        if cls.bucket.base_container is None:
            logging.debug('Base container not found - reinitializing')
            cls.bucket.setup_base()
        else:
            logging.debug('base container found')
        cls.base_container = cls.bucket.base_container
        assert(cls.base_container is not None)


    @classmethod
    def tearDownClass(cls):
        cls.base_container = None
        if not options.skip_cleanup:
            cls.bucket.destroy_all()
            shutil.rmtree(cls.test_dir)

    def tearDown(self):
        # Ensure host dirs from each test are completely destroyed.
        for host_dir in os.listdir(self.shared_host_path):
            host_dir = os.path.realpath(os.path.join(self.shared_host_path,
                                                     host_dir))
            lxc_utils.cleanup_host_mount(host_dir);


    def testInit(self):
        """Verifies that containers initialize correctly."""
        # Make a container that just points to the base container.
        container = lxc.Container.createFromExistingDir(
            self.base_container.container_path,
            self.base_container.name)
        self.assertFalse(container.is_running())


    def testInitInvalid(self):
        """Verifies that invalid containers can still be instantiated,
        if not used.
        """
        with tempfile.NamedTemporaryFile(dir=self.test_dir) as tmpfile:
            name = os.path.basename(tmpfile.name)
            container = lxc.Container.createFromExistingDir(self.test_dir, name)
            with self.assertRaises(error.ContainerError):
                container.refresh_status()


def parse_options():
    """Parse command line inputs.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Print out ALL entries.')
    parser.add_argument('--skip_cleanup', action='store_true',
                        help='Skip deleting test containers.')
    args, argv = parser.parse_known_args()

    # Hack: python unittest also processes args.  Construct an argv to pass to
    # it, that filters out the options it won't recognize.
    if args.verbose:
        argv.append('-v')
    argv.insert(0, sys.argv[0])

    return args, argv


if __name__ == '__main__':
    options, unittest_argv = parse_options()

    log_level=(logging.DEBUG if options.verbose else logging.INFO)
    unittest_logging.setup(log_level)

    unittest.main(argv=unittest_argv)
