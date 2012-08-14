# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import optparse
import os
import re
import sys

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import chrome_test, cros_ui, ownership


class desktopui_PyAutoEnduranceTests(chrome_test.PyAutoFunctionalTest):
    """Wrapper for running Chrome's PyAuto-based endurance tests."""

    _DEFAULT_TEST_LENGTH_SEC = 60 * 60 * 2  # Tests run for 2 hours.
    _DEFAULT_PERF_STATS_INTERVAL = 60 * 3  # Measure perf stats every 3 minutes.

    version = 1


    def parse_args(self, args):
        """Parses input arguments to this autotest."""
        parser = optparse.OptionParser()
        parser.add_option('--length', dest='test_length', type='int',
                          default=self._DEFAULT_TEST_LENGTH_SEC,
                          help='Number of seconds to run the endurance test. '
                               'Defaults to %default seconds.')
        parser.add_option('--interval', dest='perf_stats_interval', type='int',
                          default=self._DEFAULT_PERF_STATS_INTERVAL,
                          help='Number of seconds to wait in-between each perf '
                               'stats measurement. Defaults to %default '
                               'seconds.')
        # Preprocess the args to remove quotes before/after each one if they
        # exist.  This is necessary because arguments passed via
        # run_remote_tests.sh may be individually quoted, and those quotes must
        # be stripped before they are parsed.
        return parser.parse_args(map(lambda arg: arg.strip('\'\"'), args))


    def run_once(self, test_name, args=[]):
        """Runs the PyAuto endurance tests."""
        if isinstance(args, str):
            args = args.split()
        options, _ = self.parse_args(args)

        deps_dir = os.path.join(self.autodir, 'deps')

        # Run the PyAuto endurance tests.
        print 'About to run the pyauto endurance tests.'
        print 'Note: you will see two timestamps for each logging message.'
        print '      The outer timestamp occurs when the autotest dumps the '
        print '      pyauto output, which only occurs after all tests are '
        print '      complete. The inner timestamp is the time at which the '
        print '      message was logged by pyauto while the test was actually '
        print '      running.'
        functional_cmd = cros_ui.xcommand_as(
            '%s/chrome_test/test_src/chrome/test/functional/'
            'pyauto_functional.py %s' % (deps_dir, test_name))

        os.putenv('TEST_LENGTH', str(options.test_length))
        os.putenv('PERF_STATS_INTERVAL', str(options.perf_stats_interval))
        cmd_result = utils.run(functional_cmd, ignore_status=True,
                               stdout_tee=sys.stdout, stderr_tee=sys.stdout)
        if cmd_result.exit_status != 0:
            raise error.TestFail(
                'Pyauto returned error code %d.  This is likely because at '
                'least one pyauto test failed.  Refer to the full autotest '
                'output in desktopui_PyAutoPerfTests.DEBUG for details.'
                % cmd_result.exit_status)
