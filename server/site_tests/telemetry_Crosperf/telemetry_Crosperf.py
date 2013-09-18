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


    def run_once(self, client_ip, args, stdout='', stderr=''):
        """
        Run a single telemetry test.

        @param client_ip: The ip address of the DUT
        @param args: A dictionary of the arguments that were passed
                to this test.

        @returns A TelemetryResult instance with the results of this
                execution.

        """
        if 'iterations' in args:
            self._iterations = int(args['iterations'])
        else:
            self._iterations = 3
        self._test = args['test']

        # Look for chrome source root, either externally mounted, or inside
        # the chroot.
        if 'CHROME_ROOT' in os.environ:
            chrome_root_dir = os.environ['CHROME_ROOT']
        else:
            chrome_root_dir = '/var/cache/chromeos-chrome/chrome-src-internal'

        script_file = '%s/src/tools/perf/run_benchmark' % chrome_root_dir

        if not os.path.exists (script_file):
            raise error.TestError('run_benchmark script not found.')

        format_string = ('%s --browser=cros-chrome --remote=%s '
                         '--pageset-repeat=%d %s')
        command = format_string % (script_file, client_ip,
                                   self._iterations, self._test)
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
        self.write_perf_keyval(result.perf_keyvals)
        return result


