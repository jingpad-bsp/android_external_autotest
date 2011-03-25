# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


"""Wrapper for Google Factory Tools (gooftool).

This module provides fast access to "gooftool".
"""


import os
import glob
import subprocess
import sys
import tempfile

from autotest_lib.client.bin import factory
from autotest_lib.client.common_lib import error


GOOFTOOL_HOME = '/usr/local/gooftool'


def run(command, ignore_status=False):
    """Runs a gooftool command.

    Args:
        command: Shell command to execute.
        ignore_status: False to raise exectopion when execution result is not 0.

    Raises:
        error.TestError: The error message in "ERROR:.*" form by command.
    """
    # prepare command
    system_cmd = 'PATH="%s:$PATH" %s' % (GOOFTOOL_HOME, command)
    factory.log("Running gooftool: " + system_cmd)

    # prepare execution environment
    proc = subprocess.Popen(system_cmd,
                            stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            shell=True)
    (out, err) = proc.communicate()

    # normalize output data
    if out[-1:] == '\n':
        out = out[:-1]
    err = err.strip()

    if proc.wait() and (not ignore_status):
        # log every detail.
        out = out.strip()
        if out or err:
            message = '\n'.join([out, err])
        else:
            message = '(None)'
        factory.log('gooftool execution failed, message: ' + message)
        # try to parse "ERROR.*" from err & out.
        exception_message = [error_message for error_message in err.splitlines()
                             if error_message.startswith('ERROR')]
        exception_message = ('\n'.join(exception_message)
                             if exception_message
                             else 'Failed: %s\n%s\n%s' % (system_cmd, out, err))
        raise error.TestError(exception_message)
    if out or err:
        factory.log('gooftool results:\n%s\n%s' % (out, err))
    return out
