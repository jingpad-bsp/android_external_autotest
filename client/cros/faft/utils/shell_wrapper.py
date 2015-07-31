# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A module to abstract the shell execution environment on DUT."""

import subprocess


class ShellError(Exception):
    """Shell specific exception."""
    pass


class LocalShell(object):
    """An object to wrap the local shell environment."""

    def init(self, os_if):
        self._os_if = os_if

    def _run_command(self, cmd):
        """Helper function of run_command() methods.

        Return the subprocess.Popen() instance to provide access to console
        output in case command succeeded.
        """
        self._os_if.log('Executing %s' % cmd)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        process.wait()
        return process

    def run_command(self, cmd):
        """Run a shell command.

        In case of the command returning an error print its stdout and stderr
        outputs on the console and dump them into the log. Otherwise suppress
        all output.

        In case of command error raise an ShellError exception.
        """
        process = self._run_command(cmd)
        if process.returncode:
            err = ['Failed running: %s' % cmd]
            err.append('stdout:')
            err.append(process.stdout.read())
            err.append('stderr:')
            err.append(process.stderr.read())
            text = '\n'.join(err)
            self._os_if.log(text)
            raise ShellError('command %s failed (code: %d)' %
                             (cmd, process.returncode))

    def run_command_get_status(self, cmd):
        """Run a shell command and return its return code.

        The return code of the command is returned, in case of any error.
        """
        process = self._run_command(cmd)
        return process.returncode

    def run_command_get_output(self, cmd):
        """Run shell command and return its console output to the caller.

        The output is returned as a list of strings stripped of the newline
        characters.
        """
        process = self._run_command(cmd)
        return [x.rstrip() for x in process.stdout.readlines()]

    def read_file(self, path):
        """Read the content of the file."""
        with open(path) as f:
            return f.read()

    def write_file(self, path, data):
        """Write the data to the file."""
        with open(path, 'w') as f:
            f.write(data)

    def append_file(self, path, data):
        """Append the data to the file."""
        with open(path, 'a') as f:
            f.write(data)
