# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import subprocess
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error


class platform_Quipper(test.test):
    """
    Collects perf data and convert it to a protobuf. Verifies that quipper
    completes successfully and that the output is nonzero.
    """
    version = 1


    def run_once(self):
        """
        See test description.
        """

        # Quipper command.
        # TODO(sque): Test more event types, LBR, callgraph, etc.
        duration = 2
        quipper_command = [ 'quipper', str(duration), 'perf', 'record', '-a',
                            '-e', 'cycles' ]
        quipper_command_string = ' '.join(quipper_command)

        result = ""
        try:
            result = subprocess.check_output(quipper_command,
                                             stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            raise error.TestFail('Error running command: \"' +
                                 quipper_command_string)

        # Write keyvals.
        keyvals = {}
        keyvals['command'] = quipper_command_string;
        keyvals['result_length'] = len(result)
        self.write_perf_keyval(keyvals)

        # Verify the output size.
        if len(result) == 0:
            raise error.TestFail('Got no result data from quipper.')

