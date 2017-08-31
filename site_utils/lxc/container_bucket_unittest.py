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
