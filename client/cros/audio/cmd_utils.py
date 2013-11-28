#!/usr/bin/python
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import pipes
import subprocess


def wait_and_check_returncode(*popens):
    '''Wait for all the Popens and check the return code is 0.

    If the return code is not 0, it raises an RuntimeError.
    '''
    for p in popens:
        if p.wait() != 0:
            raise RuntimeError(
                    'Command failed(%d, %d): %s' %
                    (p.pid, p.returncode, p.command))


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
    ps = subprocess.Popen(*args, **kargs)
    the_args = args[0] if len(args) > 0 else kargs['args']
    ps.command = ' '.join(pipes.quote(x) for x in the_args)
    logging.info('Running(%d): %s', ps.pid, ps.command)
    return ps
