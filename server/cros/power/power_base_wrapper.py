# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Base class for power measurement tests with telemetry devices."""

import json
import os

from autotest_lib.client.common_lib import error
from autotest_lib.server import autotest
from autotest_lib.server import test
from autotest_lib.server.cros.dynamic_suite import suite


class PowerBaseWrapper(test.test):
    """Base class for a wrapper test around a client test.

    This wrapper test runs 1 client test given by user, and measures DUT power
    with external power measurement tools.
    """
    version = 1

    def run_once(self, host, config=None):
        """Measure power while running the client side test.

        @param host: CrosHost object representing the DUT.
        @param config: the args argument from test_that in a dict.
                       required data: {'test': 'test_TestName.tag'}
        """
        if not config:
            msg = '%s must run with args input.' % self.__class__.__name__
            raise error.TestNAError(msg)
        if 'test' not in config:
            msg = 'User did not specify client test to run in wrapper.'
            raise error.TestNAError(msg)
        # client_test_name is tagged test name.
        client_test_name = config['test']
        args_list = ['='.join((k, v)) for k, v in config.iteritems()]
        args_string = 'args = ' + json.dumps(args_list)

        # Find the client test in autotest file system.
        fs_getter = suite.create_fs_getter(self.autodir)
        predicate = suite.test_name_equals_predicate(client_test_name)
        client_test = suite.find_and_parse_tests(fs_getter, predicate)
        if not client_test:
            msg = '%s is not a valid client test name.' % client_test_name
            raise error.TestNAError(msg)

        autotest_client = autotest.Autotest(host)
        ptl = self._get_power_telemetry_logger(host, config, self.resultsdir)
        try:
            ptl.start_measurement()
            # If multiple tests with the same name are found, run the first one.
            autotest_client.run(args_string +'\n' + client_test[0].text)
        finally:
            client_test_dir = os.path.join(self.outputdir, client_test_name)
            # If client test name is not tagged in its own control file.
            if not os.path.isdir(client_test_dir):
                client_test_name = client_test_name.split('.', 1)[0]
                client_test_dir = os.path.join(self.outputdir, client_test_name)
            ptl.end_measurement(client_test_dir)

        return

    def _get_power_telemetry_logger(self, host, config, resultsdir):
        """Return the corresponding power telemetry logger.

        @param host: CrosHost object representing the DUT.
        @param config: the args argument from test_that in a dict. Settings for
                       power telemetry devices.
                       required data: {'test': 'test_TestName.tag'}
        @param resultsdir: path to directory where current autotest results are
                           stored, e.g. /tmp/test_that_results/
                           results-1-test_TestName.tag/test_TestName.tag/
                           results/
        """
        raise NotImplementedError('Subclasses must implement '
                '_get_power_telemetry_logger and return the corresponding '
                'power telemetry logger.')
