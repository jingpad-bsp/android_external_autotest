# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
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


    def _cleanup_value(self, value):
        """Cleanup a value string.

        Given a string representing a value clean it up by removing the space
        and parenthesis around the units, and either append the units or get
        rid of them.

        Examples:
            loadtime (ms) -> loadtime_ms
            image_count () -> image_count
            image_count (count) -> image_count
            CodeLoad (score (bigger is better)) -> CodeLoad_score
            load_percent (%) -> load_percent
            score (runs/s) -> score_runs_per_s

        @param value: Value we are cleaning up.

        @result a String representing the cleaned up value.
        """
        value_sections = value.split(' (')
        value_name = value_sections[0]
        # There can be sub-parens in the units -> if so remove them.
        units = value_sections[1].split('(')[0]
        units = units.split(')')[0]
        if units is '%':
            units = 'percent'
        if '/' in units:
            units = units.replace('/','_per_')
        if not units:
            return value_name
        if value_name.endswith(units):
            return value_name
        return '_'.join([value_name, units])


    def parse_benchmark_results(self):
        """Parse the results of a telemetry benchmark run.

        Stdout has the format of CSV at the top and then the output repeated
        in RESULT block format below.

        We will parse the CSV part to get the perf key-value pairs we are
        interested in.

        Example stdout:
        url,average_commit_time (ms),average_image_gathering_time (ms)
        file:///tough_scrolling_cases/cust_scrollbar.html,1.3644,0
        RESULT average_commit_time: <URL>= <SCORE> score
        RESULT average_image_gathering_time: <URL>= <SCORE> score

        We want to generate perf keys in the format of value-url i.e.:
        average_commit_time-http____www.google.com
        Where we also removed non non-alphanumeric characters except '.', '_',
        and '-'.

        Stderr has the format of Warnings/Tracebacks. There is always a default
        warning of the display enviornment setting. Followed by warnings of
        page timeouts or a traceback.

        If there are any other warnings we flag the test as warning. If there
        is a traceback we consider this test a failure.

        @param exit_code: Exit code of the the telemetry run. 0 == SUCCESS,
                          otherwise it is a warning or failure.
        @param stdout: Stdout of the telemetry run.
        @param stderr: Stderr of the telemetry run.

        @returns A TelemetryResult instance with the results of the telemetry
                 run.
        """
        # The output will be in CSV format.
        if not self._stdout:
            # Nothing in stdout implies a test failure.
            logging.error('No stdout, test failed.')
            self.status = FAILED_STATUS
            return

        stdout_lines = self._stdout.splitlines()
        value_names = None
        for line in stdout_lines:
            if not line:
                continue
            if not value_names and line.startswith('url,'):
                # This line lists out all the values we care about and we drop
                # the first one as it is the url name.
                value_names = line.split(',')[1:]
                # Clean up each value name.
                value_names = [self._cleanup_value(v) for v in value_names]
                logging.debug('Value_names: %s', value_names)
            if not value_names:
                continue
            if ' ' in line:
                # We are in a non-CSV part of the output, ignore this line.
                continue
            # We are now a CSV line we care about, parse it accordingly.
            line_values = line.split(',')
            # Grab the URL
            url = line_values[0]
            # We want the perf keys to be format value|url. Example:
            # load_time-http___www.google.com
            # Andd replace all non-alphanumeric characters except
            # '-', '.' and '_' with '_'
            url_values_names = [re.sub(r'[^\w.-]', '_', '-'.join([v, url]))
                    for v in value_names]
            self.perf_keyvals.update(dict(zip(url_values_names,
                                              line_values[1:])))
        logging.debug('Perf Keyvals: %s', self.perf_keyvals)

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
