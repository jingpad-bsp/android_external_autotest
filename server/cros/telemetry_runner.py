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


TELEMETRY_RUN_BENCHMARKS_SCRIPT = 'tools/perf/run_benchmark'
TELEMETRY_RUN_TESTS_SCRIPT = 'tools/telemetry/run_tests'
TELEMETRY_RUN_CROS_TESTS_SCRIPT = 'chrome/test/telemetry/run_cros_tests'
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

        # A list of perf values, e.g.
        # [{'graph': 'graphA', 'trace': 'page_load_time',
        #   'units': 'secs', 'value':0.5}, ...]
        self.perf_data = []
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

        Stdout has the output in RESULT block format below.

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
            elif re.search('^\d+$', value):
                value = int(value)
            else:
                value = float(value)

            self.perf_data.append({'graph':graph_name, 'trace': trace_name,
                                   'units': units, 'value': value})

        pp = pprint.PrettyPrinter(indent=2)
        logging.debug('Perf values: %s', pp.pformat(self.perf_data))

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

    def __init__(self, host, local=False):
        """Initializes this telemetry runner instance.

        If telemetry is not installed for this build, it will be.

        @param host: Host where the test will be run.
        @param local: If set, no devserver will be used, test will be run
                      locally.
        """
        self._host = host

        # TODO (llozano crbug.com/324964). Remove conditional code.
        # Use a class hierarchy instead.
        if local:
            self._setup_local_telemetry()
        else:
            self._setup_devserver_telemetry()

        logging.debug('Telemetry Path: %s', self._telemetry_path)


    def _setup_devserver_telemetry(self):
        """Setup Telemetry to use the devserver."""
        logging.debug('Setting up telemetry for devserver testing')
        logging.debug('Grabbing build from AFE.')

        build = self._host.get_build()
        if not build:
            logging.error('Unable to locate build label for host: %s.',
                          self._host.hostname)
            raise error.AutotestError('Failed to grab build for host %s.' %
                                      self._host.hostname)

        logging.debug('Setting up telemetry for build: %s', build)

        self._devserver = dev_server.ImageServer.resolve(build)
        self._telemetry_path = self._devserver.setup_telemetry(build=build)


    def _setup_local_telemetry(self):
        """Setup Telemetry to use local path to its sources.

        First look for chrome source root, either externally mounted, or inside
        the chroot.  Prefer chrome-src-internal source tree to chrome-src.
        """
        TELEMETRY_DIR = 'src'
        CHROME_LOCAL_SRC = '/var/cache/chromeos-cache/distfiles/target/'
        CHROME_EXTERNAL_SRC = '~/chrome_root/'

        logging.debug('Setting up telemetry for local testing')

        sources_list = ('chrome-src-internal', 'chrome-src')
        dir_list = [os.path.join(CHROME_EXTERNAL_SRC, x) for x in sources_list]
        dir_list.extend(
                [os.path.join(CHROME_LOCAL_SRC, x) for x in sources_list])
        if 'CHROME_ROOT' in os.environ:
            dir_list.insert(0, os.environ['CHROME_ROOT'])

        telemetry_src = ''
        for dir in dir_list:
            if os.path.exists(dir):
                telemetry_src = os.path.join(dir, TELEMETRY_DIR)
                break
        else:
            raise error.TestError('Telemetry source directory not found.')

        self._devserver = None
        self._telemetry_path = telemetry_src


    def _get_telemetry_cmd(self, script, test_or_benchmark):
        """Build command to execute telemetry based on script and benchmark.

        @param script: Telemetry script we want to run. For example:
                       [path_to_telemetry_src]/src/tools/telemetry/run_tests.
        @param test_or_benchmark: Name of the test or benchmark we want to run,
                                  with the page_set (if required) as part of
                                  the string.
        @returns Full telemetry command to execute the script.
        """
        telemetry_cmd = []
        if self._devserver:
            devserver_hostname = self._devserver.url().split(
                    'http://')[1].split(':')[0]
            telemetry_cmd.extend(['ssh', devserver_hostname])

        telemetry_cmd.extend(
                ['python',
                 script,
                 '--browser=cros-chrome',
                 '--remote=%s' % self._host.hostname,
                 test_or_benchmark])
        return telemetry_cmd


    def _run_telemetry(self, script, test_or_benchmark):
        """Runs telemetry on a dut.

        @param script: Telemetry script we want to run. For example:
                       [path_to_telemetry_src]/src/tools/telemetry/run_tests.
        @param test_or_benchmark: Name of the test or benchmark we want to run,
                                 with the page_set (if required) as part of the
                                 string.

        @returns A TelemetryResult Instance with the results of this telemetry
                 execution.
        """
        # TODO (sbasi crbug.com/239933) add support for incognito mode.

        telemetry_cmd = self._get_telemetry_cmd(script, test_or_benchmark)
        logging.debug('Running Telemetry: %s', ' '.join(telemetry_cmd))

        output = StringIO.StringIO()
        error_output = StringIO.StringIO()
        exit_code = 0
        try:
            result = utils.run(' '.join(telemetry_cmd), stdout_tee=output,
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


    def _run_test(self, script, test):
        """Runs a telemetry test on a dut.

        @param script: Which telemetry test script we want to run. Can be
                       telemetry's base test script or the Chrome OS specific
                       test script.
        @param test: Telemetry test we want to run.

        @returns A TelemetryResult Instance with the results of this telemetry
                 execution.
        """
        logging.debug('Running telemetry test: %s', test)
        telemetry_script = os.path.join(self._telemetry_path, script)
        result = self._run_telemetry(telemetry_script, test)
        if result.status is FAILED_STATUS:
            raise error.TestFail('Telemetry test: %s failed.',
                                 test)
        return result


    def run_telemetry_test(self, test):
        """Runs a telemetry test on a dut.

        @param test: Telemetry test we want to run.

        @returns A TelemetryResult Instance with the results of this telemetry
                 execution.
        """
        return self._run_test(TELEMETRY_RUN_TESTS_SCRIPT, test)


    def run_cros_telemetry_test(self, test):
        """Runs a cros specific telemetry test on a dut.

        @param test: Telemetry test we want to run.

        @returns A TelemetryResult instance with the results of this telemetry
                 execution.
        """
        return self._run_test(TELEMETRY_RUN_CROS_TESTS_SCRIPT, test)


    @staticmethod
    def _output_perf_value(perf_value_writer, perf_data):
        """Output perf values to result dir.

        The perf values will be output to the result dir and
        be subsequently uploaded to perf dashboard.

        @param perf_value_writer: Should be an instance with the function
                                  output_perf_value(), if None, no perf value
                                  will be written. Typically this will be the
                                  job object from an autotest test.
        @param perf_data: A list of perf values, each value is
                          a dictionary that looks like
                          {'graph':'GraphA', 'trace':'metric1',
                           'units':'secs', 'value':0.5}
        """
        for perf_value in perf_data:
            perf_value_writer.output_perf_value(
                    description=perf_value['trace'],
                    value=perf_value['value'],
                    units=perf_value['units'],
                    graph=perf_value['graph'])


    def run_telemetry_benchmark(self, benchmark, perf_value_writer=None):
        """Runs a telemetry benchmark on a dut.

        @param benchmark: Benchmark we want to run.
        @param perf_value_writer: Should be an instance with the function
                                  output_perf_value(), if None, no perf value
                                  will be written. Typically this will be the
                                  job object from an autotest test.

        @returns A TelemetryResult Instance with the results of this telemetry
                 execution.
        """
        logging.debug('Running telemetry benchmark: %s', benchmark)
        telemetry_script = os.path.join(self._telemetry_path,
                                        TELEMETRY_RUN_BENCHMARKS_SCRIPT)
        result = self._run_telemetry(telemetry_script, benchmark)
        result.parse_benchmark_results()

        if perf_value_writer:
            self._output_perf_value(perf_value_writer, result.perf_data)

        if result.status is WARNING_STATUS:
            raise error.TestWarn('Telemetry Benchmark: %s'
                                 ' exited with Warnings.' % benchmark)
        if result.status is FAILED_STATUS:
            raise error.TestFail('Telemetry Benchmark: %s'
                                 ' failed to run.' % benchmark)

        return result
