# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.common_lib import error
from autotest_lib.server import autotest
from autotest_lib.server import test
from autotest_lib.server.cros.dynamic_suite import suite
from autotest_lib.server.cros.power import power_telemetry_logger


class power_MeasurementWrapper(test.test):
    """Wrapper test around a client test.

    This wrapper test runs 1 client test given by user, and measures DUT power
    with telemetry devices (Sweetberry).
    """
    version = 1

    def run_once(self, host=None, config_list=None):
        """Measure power while running the client side test.

        @param host: the DUT.
        @param config_list: the args argument from test_that in a list,
                            delimited by space.
        """
        if not config_list:
            msg = 'power_MeasurementWrapper cannot run without args input.'
            raise error.TestNAError(msg)
        config = dict(item.replace(':', '=').split('=', 1)
                      for item in config_list)
        if 'test' not in config:
            msg = 'User did not specify client test to run in wrapper.'
            raise error.TestNAError(msg)
        # client_test_name is tagged test name.
        client_test_name = config['test']

        # Find the client test in autotest file system.
        fs_getter = suite.create_fs_getter(self.autodir)
        predicate = suite.test_name_equals_predicate(client_test_name)
        client_test = suite.find_and_parse_tests(fs_getter, predicate)
        if not client_test:
            msg = '%s is not a valid client test name.' % client_test_name
            raise error.TestNAError(msg)

        autotest_client = autotest.Autotest(host)
        ptl = power_telemetry_logger.PowerTelemetryLogger(
                config, self.outputdir, host)
        try:
            ptl.start_measurement()
            # If multiple tests with the same name are found, run the first one.
            autotest_client.run(client_test[0].text)
        finally:
            client_test_dir = os.path.join(self.outputdir, client_test_name)
            # If client test name is not tagged.
            if not os.path.isdir(client_test_dir):
                client_test_name = client_test_name.split('.', 1)[0]
            client_test_debug_file = os.path.join(self.outputdir,
                                                  client_test_name, 'debug',
                                                  '%s.DEBUG' % client_test_name)
            ptl.end_measurement(client_test_debug_file)

        return
