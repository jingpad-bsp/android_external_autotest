# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import pprint
import re
import StringIO

import common
from autotest_lib.client.common_lib import error, utils
from autotest_lib.client.common_lib.cros import dev_server


TELEMETRY_RUN_BENCHMARKS_SCRIPT = 'tools/perf/run_multipage_benchmarks'
TELEMETRY_RUN_TESTS_SCRIPT = 'tools/telemetry/run_tests'
TELEMETRY_TIMEOUT_MINS = 60

# Result Statuses
SUCCESS_STATUS = 'SUCCESS'
WARNING_STATUS = 'WARNING'
FAILED_STATUS = 'FAILED'

# Regex for the RESULT output lines understood by chrome buildbot.
# Keep in sync with chromium/tools/build/scripts/slave/process_log_utils.py.
RESULTS_REGEX = re.compile(r'(?P<IMPORTANT>\*)?RESULT '
                             '(?P<GRAPH>[^:]*): (?P<TRACE>[^=]*)= '
                             '(?P<VALUE>[\{\[]?[-\d\., ]+[\}\]]?)('
                             ' ?(?P<UNITS>.+))?')

# Constants pertaining to perf keys generated from Telemetry test results.
PERF_KEY_TELEMETRY_PREFIX = 'TELEMETRY'
PERF_KEY_DELIMITER = '--'


class TelemetryResult(object):
    """Class to represent the results of a telemetry run.

    This class represents the results of a telemetry run, whether it ran
    successful, failed or had warnings.
    """


    def __init__(self, exit_code=0, stdout='', stderr=''):
        """Initializes this TelemetryResultObject instance.

        @param status: Status of the telemtry run.
        @param stdout: Stdout of the telemetry run.
        @param stderr: Stderr of the telemetry run.
        """
        if exit_code == 0:
            self.status = SUCCESS_STATUS
        else:
            self.status = FAILED_STATUS

        self.perf_keyvals = {}
        self._stdout = stdout
        self._stderr = stderr
        self.output = '\n'.join([stdout, stderr])


    def _cleanup_perf_string(self, str):
        """Clean up a perf-related string by removing illegal characters.

        Perf keys stored in the chromeOS database may contain only letters,
        numbers, underscores, periods, and dashes.  Transform an inputted
        string so that any illegal characters are replaced by underscores.

        @param str: The perf string to clean up.

        @return The cleaned-up perf string.
        """
        return re.sub(r'[^\w.-]', '_', str)


    def _cleanup_units_string(self, units):
        """Cleanup a units string.

        Given a string representing units for a perf measurement, clean it up
        by replacing certain illegal characters with meaningful alternatives.
        Any other illegal characters should then be replaced with underscores.

        Examples:
            count/time -> count_per_time
            % -> percent
            units! --> units_
            score (bigger is better) -> score__bigger_is_better_
            score (runs/s) -> score__runs_per_s_

        @param units: The units string to clean up.

        @return The cleaned-up units string.
        """
        if '%' in units:
            units = units.replace('%', 'percent')
        if '/' in units:
            units = units.replace('/','_per_')
        return self._cleanup_perf_string(units)


    def parse_benchmark_results(self):
        """Parse the results of a telemetry benchmark run.

        Stdout has the format of CSV at the top and then the output repeated
        in RESULT block format below.

        The lines of interest start with the substring "RESULT".  These are
        specially-formatted perf data lines that are interpreted by chrome
        builbot (when the Telemetry tests run for chrome desktop) and are
        parsed to extract perf data that can then be displayed on a perf
        dashboard.  This format is documented in the docstring of class
        GraphingLogProcessor in this file in the chrome tree:

        chromium/tools/build/scripts/slave/process_log_utils.py

        Example RESULT output lines:
        RESULT average_commit_time_by_url: http___www.ebay.com= 8.86528 ms
        RESULT CodeLoad: CodeLoad= 6343 score (bigger is better)
        RESULT ai-astar: ai-astar= [614,527,523,471,530,523,577,625,614,538] ms

        Currently for chromeOS, we can only associate a single perf key (string)
        with a perf value.  That string can only contain letters, numbers,
        dashes, periods, and underscores, as defined by write_keyval() in:

        chromeos/src/third_party/autotest/files/client/common_lib/
        base_utils.py

        We therefore parse each RESULT line, clean up the strings to remove any
        illegal characters not accepted by chromeOS, and construct a perf key
        string based on the parsed components of the RESULT line (with each
        component separated by a special delimiter).  We prefix the perf key
        with the substring "TELEMETRY" to identify it as a telemetry-formatted
        perf key.

        Stderr has the format of Warnings/Tracebacks. There is always a default
        warning of the display enviornment setting, followed by warnings of
        page timeouts or a traceback.

        If there are any other warnings we flag the test as warning. If there
        is a traceback we consider this test a failure.
        """
        if not self._stdout:
            # Nothing in stdout implies a test failure.
            logging.error('No stdout, test failed.')
            self.status = FAILED_STATUS
            return

        stdout_lines = self._stdout.splitlines()
        for line in stdout_lines:
            results_match = RESULTS_REGEX.search(line)
            if not results_match:
                continue

            match_dict = results_match.groupdict()
            graph_name = self._cleanup_perf_string(match_dict['GRAPH'].strip())
            trace_name = self._cleanup_perf_string(match_dict['TRACE'].strip())
            units = self._cleanup_units_string(
                    (match_dict['UNITS'] or 'units').strip())
            value = match_dict['VALUE'].strip()
            unused_important = match_dict['IMPORTANT'] or False  # Unused now.

            if value.startswith('['):
                # A list of values, e.g., "[12,15,8,7,16]".  Extract just the
                # numbers, compute the average and use that.  In this example,
                # we'd get 12+15+8+7+16 / 5 --> 11.6.
                value_list = [float(x) for x in value.strip('[],').split(',')]
                value = float(sum(value_list)) / len(value_list)
            elif value.startswith('{'):
                # A single value along with a standard deviation, e.g.,
                # "{34.2,2.15}".  Extract just the value itself and use that.
                # In this example, we'd get 34.2.
                value_list = [float(x) for x in value.strip('{},').split(',')]
                value = value_list[0]  # Position 0 is the value.

            perf_key = PERF_KEY_DELIMITER.join(
                    [PERF_KEY_TELEMETRY_PREFIX, graph_name, trace_name, units])
            self.perf_keyvals[perf_key] = str(value)

        pp = pprint.PrettyPrinter(indent=2)
        logging.debug('Perf Keyvals: %s', pp.pformat(self.perf_keyvals))

        if self.status is SUCCESS_STATUS:
            return

        # Otherwise check if simply a Warning occurred or a Failure,
        # i.e. a Traceback is listed.
        self.status = WARNING_STATUS
        for line in self._stderr.splitlines():
            if line.startswith('Traceback'):
                self.status = FAILED_STATUS


class TelemetryRunner(object):
    """Class responsible for telemetry for a given build.

    This class will extract and install telemetry on the devserver and is
    responsible for executing the telemetry benchmarks and returning their
    output to the caller.
    """

    def __init__(self, host):
        """Initializes this telemetry runner instance.

        If telemetry is not installed for this build, it will be.
        """
        self._host = host
        logging.debug('Grabbing build from AFE.')

        build = host.get_build()
        if not build:
            logging.error('Unable to locate build label for host: %s.',
                          self._host.hostname)
            raise error.AutotestError('Failed to grab build for host %s.' %
                                      self._host.hostname)

        logging.debug('Setting up telemetry for build: %s', build)

        self._devserver = dev_server.ImageServer.resolve(build)
        self._telemetry_path = self._devserver.setup_telemetry(build=build)
        logging.debug('Telemetry Path: %s',self._telemetry_path)


    def _run_telemetry(self, script, test_or_benchmark):
        """Runs telemetry on a dut.

        @param script: Telemetry script we want to run. For example:
                       [path_to_telemetry_src]/src/tools/telemetry/run_tests
        @param test_or_benchmark: Name of the test or benchmark we want to run,
                                 with the page_set (if required) as part of the
                                 string.

        @returns A TelemetryResult Instance with the results of this telemetry
                 execution.
        """
        devserver_hostname = self._devserver.url().split(
                'http://')[1].split(':')[0]
        telemetry_args = ['ssh',
                          devserver_hostname,
                          'python',
                          script,
                          '--browser=cros-chrome',
                          '--remote=%s' % self._host.hostname,
                          test_or_benchmark]

        logging.debug('Running Telemetry: %s', ' '.join(telemetry_args))
        output = StringIO.StringIO()
        error_output = StringIO.StringIO()
        exit_code = 0
        try:
            result = utils.run(' '.join(telemetry_args), stdout_tee=output,
                               stderr_tee=error_output,
                               timeout=TELEMETRY_TIMEOUT_MINS*60)
            exit_code = result.exit_status
        except error.CmdError as e:
            # Telemetry returned a return code of not 0; for benchmarks this
            # can be due to a timeout on one of the pages of the page set and
            # we may still have data on the rest. For a test however this
            # indicates failure.
            logging.debug('Error occurred executing telemetry.')
            exit_code = e.result_obj.exit_status

        stdout = output.getvalue()
        stderr = error_output.getvalue()
        logging.debug('Telemetry completed with exit code: %d.\nstdout:%s\n'
                      'stderr:%s', exit_code, stdout, stderr)

        return TelemetryResult(exit_code=exit_code, stdout=stdout,
                               stderr=stderr)


    def run_telemetry_test(self, test):
        """Runs a telemetry test on a dut.

        @param test: Telemetry test we want to run.

        @returns A TelemetryResult Instance with the results of this telemetry
                 execution.
        """
        logging.debug('Running telemetry test: %s', test)
        telemetry_script = os.path.join(self._telemetry_path,
                                        TELEMETRY_RUN_TESTS_SCRIPT)
        result = self._run_telemetry(telemetry_script, test)
        if result.status is FAILED_STATUS:
            raise error.TestFail('Telemetry test: %s failed.',
                                 test)
        return result


    def run_telemetry_benchmark(self, benchmark, page_set, keyval_writer=None):
        """Runs a telemetry benchmark on a dut.

        @param benchmark: Benchmark we want to run.
        @param page_set: Page set we want to use.
        @param keyval_writer: Should be a instance with the function
                              write_perf_keyval(), if None, no keyvals will be
                              written. Typically this will be the job object
                              from a autotest test.

        @returns A TelemetryResult Instance with the results of this telemetry
                 execution.
        """
        logging.debug('Running telemetry benchmark: %s with page set: %s.',
                      benchmark, page_set)
        telemetry_script = os.path.join(self._telemetry_path,
                                        TELEMETRY_RUN_BENCHMARKS_SCRIPT)
        page_set_path = os.path.join(self._telemetry_path,
                                     'tools/perf/page_sets/%s' % page_set)
        benchmark_with_pageset = ' '.join([benchmark, page_set_path])
        result = self._run_telemetry(telemetry_script, benchmark_with_pageset)
        result.parse_benchmark_results()

        if keyval_writer:
            keyval_writer.write_perf_keyval(result.perf_keyvals)

        if result.status is WARNING_STATUS:
            raise error.TestWarn('Telemetry Benchmark: %s with page set: %s'
                                 ' exited with Warnings.' % (benchmark,
                                                             page_set))
        if result.status is FAILED_STATUS:
            raise error.TestFail('Telemetry Benchmark: %s with page set: %s'
                                 ' failed to run.' % (benchmark,
                                                      page_set))

        return result
