# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils


class ProcessWatcher(object):
    """Start a process, and terminate it later."""

    def __init__(self, command, args=[], host=None):
        """Construst a ProcessWatcher without starting the process.

        @param command: string command to use to start and stop the process.
        @param args: list of strings to pass to the command.
        @param host: host object if the server should be started on a remote
                host.

        """
        self._command = command
        self._args = args
        self._run = utils.run if host is None else host.run


    def start(self):
        """Start a (potentially remote) instance of the process."""
        self._run('%s %s &' % (self._command, ' '.join(self._args)))


    def close(self, timeout_seconds=40):
        """Close the (potentially remote) instance of the process.

        @param timeout_seconds: int number of seconds to wait for shutdown.

        """
        self._run('pkill -f --signal TERM %s' % self._command,
                  ignore_status=True)
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            result = self._run('pgrep -l %s' % self._command,
                               ignore_status=True)
            if result.exit_status != 0:
                return
            time.sleep(0.3)
        raise error.TestError('Timed out waiting for %s to die.' %
                              self._command)
