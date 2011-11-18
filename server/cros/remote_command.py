# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Based on site_wifitest.py's "HelperThreead"
import logging, shlex, threading

class _HelperThread(threading.Thread):
    """Make a thread to run the command in."""
    def __init__(self, target, cmd):
        threading.Thread.__init__(self)
        self.target = target
        self.cmd = cmd

    def run(self):
        logging.info('Helper thread running: %s' % self.cmd)
        # NB: set ignore_status as we're always terminated w/ pkill
        self.result = self.target.run(self.cmd, ignore_status=True)


class Command(object):
    """Encapsulates a command run on a remote machine.

    Future work is to have this get the PID (by prepending 'echo $$;
    exec' to the command and parsing the output).

    This class supports the context management protocol, so you can
    pass it to the with statement.
    """
    def __init__(self, target, cmd):
        """Runs cmd (a string) on target (a host object)."""
        self.command_name = shlex.split(cmd)[0]
        self.target = target
        self.thread = _HelperThread(self.target, cmd)
        self.thread.start()

    def Join(self):
        """Kills the remote command and waits until it dies."""
        # Ignore status because the command may have exited already
        self.target.run("pkill %s" % self.command_name,
                        ignore_status=True)
        self.thread.join()

    def __enter__(self):
        return self

    def __exit__(self, exception, value, traceback):
        self.Join()
        return False
