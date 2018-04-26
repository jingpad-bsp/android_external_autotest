# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Definition of a CrOS suite in skylab.

This file is a simplicication of dynamic_suite.suite without any useless
features for skylab suite.

Suite class in this file mainly has 2 features:
    1. Integrate parameters from control file & passed in arguments.
    2. Find proper child tests for a given suite.

Use case:
    See _run_suite() in skylab_suite.run_suite_skylab.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import collections

from lucifer import autotest


SuiteSpecs = collections.namedtuple(
        'SuiteSpecs',
        [
                'builds',
                'test_source_build',
        ])


class Suite(object):
    """The class for a CrOS suite."""

    def __init__(self, specs):
        """Initialize a suite.

        @param specs: A SuiteSpecs object.
        """
        self.tests = []
        self.wait = True
        self.builds = specs.builds
        self.test_source_build = specs.test_source_build


    def stage_suite_artifacts(self):
        """Stage suite control files and suite-to-tests mapping file.

        @param build: The build to stage artifacts.
        """
        suite_common = autotest.load('server.cros.dynamic_suite.suite_common')
        ds, _ = suite_common.stage_build_artifacts(self.test_source_build)
        self.ds = ds


    def get_suite_args(self):
        """Get the suite args.

        The suite args includes:
            a. suite args in suite control file.
            b. passed-in suite args by user.
        """
        return
