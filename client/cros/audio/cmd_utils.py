#!/usr/bin/python
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import pipes
import subprocess
import threading

_popen_lock = threading.Lock()


def kill_or_log_returncode(*popens):
    '''Kills all the processes of the given Popens or logs the return code.

    @param poopens: The Popens to be killed.
    '''
    for p in popens:
        if p.poll() is None:
            try:
                p.kill()
            except Exception as e:
                logging.warning('failed to kill %d, %s', p.pid, e)
        else:
            logging.warning('command exit (pid=%d, rc=%d): %s',
                            p.pid, p.returncode, p.command)


def wait_and_check_returncode(*popens):
    '''Wait for all the Popens and check the return code is 0.

    If the return code is not 0, it raises an RuntimeError.

    @param popens: The Popens to be checked.
    '''
    error_message = None
    for p in popens:
        if p.wait() != 0:
            error_message = ('Command failed(%d, %d): %s' %
                             (p.pid, p.returncode, p.command))
            logging.error(error_message)
    if error_message:
        raise RuntimeError(error_message)


def execute(args, stdin=None, stdout=None):
    '''Executes a child command and wait for it.

    Returns the output from standard output if 'stdout' is subprocess.PIPE.
    Raises RuntimeException if the return code of the child command is not 0.

    @param args: the command to be executed
    @param stdin: the executed program's standard input
    @param stdout: the executed program's stdandrd output
    '''
    ps = popen(args, stdin=stdin, stdout=stdout)
    out = ps.communicate()[0] if stdout == subprocess.PIPE else None
    wait_and_check_returncode(ps)
    return out


def popen(*args, **kargs):
    '''Returns a Popen object just as subprocess.Popen does but with the
    executed command stored in Popen.command.
    '''
    # The lock is required for http://crbug.com/323843.
    the_args = args[0] if len(args) > 0 else kargs['args']
    command = ' '.join(pipes.quote(x) for x in the_args)
    logging.info('Running: %s', command)
    with _popen_lock:
        ps = subprocess.Popen(*args, **kargs)
    ps.command = command
    logging.info('pid: %d', ps.pid)
    return ps
