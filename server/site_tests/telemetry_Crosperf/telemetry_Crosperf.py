# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import os
import StringIO

import common
from autotest_lib.client.common_lib import error
from autotest_lib.server import test
from autotest_lib.server import utils
from autotest_lib.server.cros import telemetry_runner

TELEMETRY_TIMEOUT_MINS = 60

class telemetry_Crosperf(test.test):
    """
    Run one or more telemetry benchmarks under the crosperf script.

    """
    version = 1
    CHROME_SRC_ROOT = '/var/cache/chromeos-cache/distfiles/target/'


    def run_once(self, client_ip, args, stdout='', stderr=''):
        """
        Run a single telemetry test.

        @param client_ip: The ip address of the DUT
        @param args: A dictionary of the arguments that were passed
                to this test.

        @returns A TelemetryResult instance with the results of this
                execution.

        """
        self._test = args['test']
        self._test_args = ''
        if 'test_args' in args:
            self._test_args = args['test_args']

        # Look for chrome source root, either externally mounted, or inside
        # the chroot.  Prefer chrome-src-internal source tree to chrome-src.
        sources_list = ('chrome-src-internal', 'chrome-src')

        dir_list = [os.path.join(self.CHROME_SRC_ROOT, x) for x in sources_list]
        if 'CHROME_ROOT' in os.environ:
            dir_list.insert(0, os.environ['CHROME_ROOT'])

        for dir in dir_list:
            if os.path.exists(dir):
                chrome_root_dir = dir
                break
        else:
            raise error.TestError('Chrome source directory not found.')

        logging.info('Using Chrome source tree at %s', chrome_root_dir)
        format_string = ('%s/src/tools/perf/run_benchmark '
                         '--browser=cros-chrome --remote=%s '
                         '%s %s')
        command = format_string % (chrome_root_dir, client_ip,
                                   self._test_args, self._test)
        logging.info('CMD: %s', command)

        output = StringIO.StringIO()
        error_output = StringIO.StringIO()
        exit_code = 0

        try:
            result = utils.run(command, stdout_tee=output,
                               stderr_tee=error_output,
                               timeout=TELEMETRY_TIMEOUT_MINS*60)
            exit_code = result.exit_status
        except error.CmdError as e:
            logging.debug('Error occurred executing telemetry.')
            exit_code = e.result_obj.exit_status
            raise error.TestFail ('An error occurred while executing'
                                  ' telemetry test.')

        stdout = output.getvalue()
        stderr = error_output.getvalue()
        logging.debug('Telemetry completed with exit code: %d.'
                      '\nstdout:%s\nstderr:%s', exit_code, stdout,
                      stderr)
        logging.info('Telemetry completed with exit code: %d.'
                     '\nstdout:%s\nstderr:%s', exit_code, stdout,
                     stderr)

        result = telemetry_runner.TelemetryResult(exit_code=exit_code,
                                                  stdout=stdout,
                                                  stderr=stderr)

        result.parse_benchmark_results()
        for data in result.perf_data:
            self.output_perf_value(description=data['trace'],
                                   value=data['value'],
                                   units=data['units'],
                                   graph=data['graph'])

        return result
