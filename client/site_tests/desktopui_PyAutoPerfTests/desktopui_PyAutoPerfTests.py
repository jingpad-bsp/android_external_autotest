# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import optparse
import os
import re
import sys

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.perf_expectations import expectation_checker
from autotest_lib.client.cros import chrome_test, cros_ui


class desktopui_PyAutoPerfTests(chrome_test.PyAutoFunctionalTest):
    """Wrapper for running Chrome's PyAuto-based performance tests.

    Performs all setup and fires off the PERFORMANCE PyAuto suite for ChromeOS.
    """

    _PERF_MARKER_PRE = '_PERF_PRE_'
    _PERF_MARKER_POST = '_PERF_POST_'
    _DEFAULT_NUM_ITERATIONS = 10  # Keep synced with perf.py.

    version = 1


    def initialize(self):
        chrome_test.PyAutoFunctionalTest.initialize(self)

        # The next few lines install the page_cycler depdendency onto the
        # target.  It is very similar to what happens in the above
        # function call except that chrome_test is installing the
        # chrome_test dep.
        dep = 'page_cycler_dep'
        dep_dir = os.path.join(self.autodir, 'deps', dep)
        self.job.install_pkg(dep, 'dep', dep_dir)
        try:
            setup_cmd = '/bin/sh %s/%s' % (dep_dir,
                                           'setup_test_links.sh')
            utils.system(setup_cmd)  # this might raise an exception
        except error.CmdError as e:
            raise error.TestError(e)


    def parse_args(self, args):
        """Parses input arguments to this autotest."""
        parser = optparse.OptionParser()
        parser.add_option('--iterations', dest='num_iterations', type='int',
                          default=self._DEFAULT_NUM_ITERATIONS,
                          help='Number of iterations for perf measurements. '
                               'Defaults to %default iterations.')
        parser.add_option('--max-timeouts', dest='max_timeouts', type='int',
                          default=0,
                          help='Maximum number of automation timeouts to '
                               'ignore before failing the test. Defaults to '
                               'the value given in perf.py.')
        parser.add_option('--suite', dest='suite', type='string',
                          default='PERFORMANCE',
                          help='Name of the suite to run, as specified in the '
                               '"PYAUTO_TESTS" suite file. Defaults to '
                               '%default, which runs all perf tests.')
        parser.add_option('--pgo', dest='pgo', action='store_true',
                          default=False,
                          help='Run the suite under PGO mode. In the PGO '
                               'mode, the renderer cleanly exits and '
                               'sandbox is turned off.')
        # Preprocess the args to remove quotes before/after each one if they
        # exist.  This is necessary because arguments passed via
        # run_remote_tests.sh may be individually quoted, and those quotes must
        # be stripped before they are parsed.
        return parser.parse_args(map(lambda arg: arg.strip('\'\"'), args))


    def run_once(self, args=[]):
        """Runs the PyAuto performance tests."""
        if isinstance(args, str):
          args = args.split()
        options, test_args = self.parse_args(args)
        test_args = ' '.join(test_args)

        deps_dir = os.path.join(self.autodir, 'deps')

        # Run the PyAuto performance tests.
        print 'About to run the pyauto performance tests.'
        print 'Note: you will see two timestamps for each logging message.'
        print '      The outer timestamp occurs when the autotest dumps the '
        print '      pyauto output, which only occurs after all tests are '
        print '      complete. The inner timestamp is the time at which the '
        print '      message was logged by pyauto while the test was actually '
        print '      running.'
        functional_cmd = cros_ui.xcommand_as(
            '%s/chrome_test/test_src/chrome/test/functional/'
            'pyauto_functional.py --suite=%s %s' % (
                deps_dir, options.suite, test_args))

        os.putenv('NUM_ITERATIONS', str(options.num_iterations))
        self.write_perf_keyval({'iterations': options.num_iterations})

        if options.max_timeouts:
            os.putenv('MAX_TIMEOUT_COUNT', str(options.max_timeouts))

        if options.pgo:
            os.putenv('USE_PGO', '1')

        cmd_result = utils.run(functional_cmd, ignore_status=True,
                               stdout_tee=sys.stdout, stderr_tee=sys.stdout)
        output = cmd_result.stdout + '\n' + cmd_result.stderr

        # Output perf keyvals for any perf results recorded during the tests.
        re_compiled = re.compile('%s(.+)%s' % (self._PERF_MARKER_PRE,
                                               self._PERF_MARKER_POST))
        perf_lines = [line for line in output.split('\n')
                      if re_compiled.match(line)]
        if perf_lines:
            perf_dict = dict([eval(re_compiled.match(line).group(1))
                              for line in perf_lines])
            self.write_perf_keyval(perf_dict)

        # Fail the autotest if any pyauto tests failed.  This is done after
        # writing perf keyvals so that any computed results from passing tests
        # are still graphed.
        if cmd_result.exit_status != 0:
            raise error.TestFail(
                'Pyauto returned error code %d.  This is likely because at '
                'least one pyauto test failed.  Refer to the full autotest '
                'output in desktopui_PyAutoPerfTests.DEBUG for details.'
                % cmd_result.exit_status)

        # TODO(dennisjeffrey): need further investigation on where
        # we should put the checking logic, i.e. integrated
        # with autotest or in each individual test.
        checker = expectation_checker.perf_expectation_checker(
                self.__class__.__name__)
        result = checker.compare_multiple_traces(perf_dict)
        if result['regress']:
            raise error.TestFail('Pyauto perf tests regression detected: %s' %
                                 result['regress'])
        if result['improve']:
            raise error.TestWarn('Pyauto perf tests improvement detected: %s' %
                                 result['improve'])
