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
import logging

from lucifer import autotest
from skylab_suite import swarming_lib


SuiteSpecs = collections.namedtuple(
        'SuiteSpecs',
        [
                'builds',
                'suite_name',
                'suite_file_name',
                'test_source_build',
                'suite_args',
                'timeout_mins',
        ])


class NonValidPropertyError(Exception):
  """Raised if a suite's property is not valid."""


class RetryHandler(object):
    """The class for handling retries for a CrOS suite."""

    def __init__(self, provision_num_required=0):
        self.provision_num_required = provision_num_required
        self._active_child_tasks = []


    def handle_results(self, all_tasks):
        """Handle child tasks' results."""
        self._active_child_tasks = all_tasks


    def finished_waiting(self):
        """Check whether the suite should finish its waiting."""
        if self.provision_num_required > 0:
            successfully_completed_bots = set()
            for t in self._active_child_tasks:
                if (t['state'] == swarming_lib.TASK_COMPLETED and
                    (not t['failure'])):
                    successfully_completed_bots.add(t['bot_id'])

            logging.info('Found %d successfully provisioned bots',
                         len(successfully_completed_bots))
            return (len(successfully_completed_bots) >
                    self.provision_num_required)

        finished_tasks = [t for t in self._active_child_tasks if t['state'] in
                          swarming_lib.TASK_FINISHED_STATUS]
        logging.info('%d/%d child tasks finished',
                     len(finished_tasks), len(self._active_child_tasks))
        return len(finished_tasks) == len(self._active_child_tasks)


class Suite(object):
    """The class for a CrOS suite."""

    def __init__(self, specs):
        """Initialize a suite.

        @param specs: A SuiteSpecs object.
        """
        self._ds = None

        self.control_file = ''
        self.tests = []
        self.wait = True
        self.builds = specs.builds
        self.test_source_build = specs.test_source_build
        self.suite_name = specs.suite_name
        self.suite_file_name = specs.suite_file_name
        self.suite_id = None
        self.timeout_mins = specs.timeout_mins

        self.retry_handler = RetryHandler()


    @property
    def ds(self):
        """Getter for private |self._ds| property.

        This ensures that once self.ds is called, there's a devserver ready
        for it.
        """
        if self._ds is None:
            raise NonValidPropertyError(
                'Property self.ds is None. Please call stage_suite_artifacts() '
                'before calling it.')

        return self._ds


    def prepare(self):
        """Prepare a suite job for execution."""
        self._stage_suite_artifacts()
        self._parse_suite_args()
        self._find_tests()


    def _stage_suite_artifacts(self):
        """Stage suite control files and suite-to-tests mapping file.

        @param build: The build to stage artifacts.
        """
        suite_common = autotest.load('server.cros.dynamic_suite.suite_common')
        ds, _ = suite_common.stage_build_artifacts(self.test_source_build)
        self._ds = ds


    def _parse_suite_args(self):
        """Get the suite args.

        The suite args includes:
            a. suite args in suite control file.
            b. passed-in suite args by user.
        """
        suite_common = autotest.load('server.cros.dynamic_suite.suite_common')
        self.control_file = suite_common.get_control_file_by_build(
                self.test_source_build, self.ds, self.suite_file_name)


    def _find_tests(self):
        """Fetch the child tests."""
        control_file_getter = autotest.load(
                'server.cros.dynamic_suite.control_file_getter')
        suite_common = autotest.load('server.cros.dynamic_suite.suite_common')

        cf_getter = control_file_getter.DevServerGetter(
                self.test_source_build, self.ds)
        tests = suite_common.retrieve_for_suite(
                cf_getter, self.suite_name)
        self.tests = suite_common.filter_tests(tests)


class ProvisionSuite(Suite):
    """The class for a CrOS provision suite."""

    def __init__(self, specs):
        super(ProvisionSuite, self).__init__(specs)
        self._num_required = specs.suite_args['num_required']
        # TODO (xixuan): Ideally the dynamic_suite service is designed
        # to be decoupled with any lab (RPC) calls. Here to set maximum
        # DUT number for provision as 10 first.
        self._num_max = 2
        self.retry_handler = RetryHandler(self._num_required)


    def _find_tests(self):
        """Fetch the child tests for provision suite."""
        control_file_getter = autotest.load(
                'server.cros.dynamic_suite.control_file_getter')
        suite_common = autotest.load('server.cros.dynamic_suite.suite_common')

        cf_getter = control_file_getter.DevServerGetter(
                self.test_source_build, self.ds)
        dummy_test = suite_common.retrieve_control_data_for_test(
                cf_getter, 'dummy_Pass')
        self.tests = [dummy_test] * max(self._num_required, self._num_max)
