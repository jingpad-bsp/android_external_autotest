# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import pipes
import threading


class _HelperThread(threading.Thread):
    """Make a thread to run the command in."""
    def __init__(self, host, cmd):
        super(_HelperThread, self).__init__()
        self._host = host
        self._cmd = cmd
        self._result = None
        self.daemon = True


    def run(self):
        logging.info('Helper thread running: %s', self._cmd)
        # NB: set ignore_status as we're always terminated w/ pkill
        self._result = self._host.run(self._cmd, ignore_status=True)


    @property
    def result(self):
        """
        @returns string result of running our command if the command has
                finished, and None otherwise.

        """
        return self._result


class Command(object):
    """
    Encapsulates a command run on a remote machine.

    Future work is to have this get the PID (by prepending 'echo $$;
    exec' to the command and parsing the output).

    """
    def __init__(self, host, cmd, pkill_argument=None):
        """
        Run a command on a remote host in the background.

        @param host Host object representing the remote machine.
        @param cmd String command to run on the remote machine.
        @param pkill_argument String argument to pkill to kill the remote
                process.

        """
        if pkill_argument is None:
            pkill_argument = os.path.basename(cmd)
        self._command_name = pipes.quote(pkill_argument)
        self._host = host
        self._thread = _HelperThread(self._host, cmd)
        self._thread.start()


    def join(self, signal=None):
        """
        Kills the remote command and waits until it dies.  Takes an optional
        signal argument to control which signal to send the process to be
        killed.

        @param signal Signal string to give to pkill (e.g. SIGNAL_INT).
        """
        if signal is None:
            signal_arg = ''
        else:
            # In theory, it should be hard to pass something evil for signal if
            # we make sure it's an integer before passing it to pkill.
            signal_arg = '-' + str(int(signal))

        # Ignore status because the command may have exited already
        self._host.run("pkill %s %s" % (signal_arg, self._command_name),
                       ignore_status=True)
        self._thread.join()


    def __enter__(self):
        return self


    def __exit__(self, exception, value, traceback):
        self.join()
        return False


    @property
    def result(self):
        """
        @returns string result of running our command if the command has
                finished, and None otherwise.

        """
        return self._thread.result
