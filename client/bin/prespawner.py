# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


'''
A library to prespawn autotest processes to minimize startup overhead.
'''

import cPickle as pickle, os, sys


if len(sys.argv) == 2 and sys.argv[1] == '--prespawn_autotest':
    # Run an autotest process, and on stdin, wait for a pickled environment +
    # argv (as a tuple); see spawn() below.  Once we receive these, start
    # autotest.

    # Do common imports (to save startup time).
    # pylint: disable=W0611
    import common
    import autotest_lib.client.bin.job
    # Wait for environment and autotest arguments.
    env, sys.argv = pickle.load(sys.stdin)
    # Run autotest and exit.
    if env:
        os.environ.clear()
        os.environ.update(env)
        execfile('autotest')
    sys.exit(0)


import logging, subprocess, threading
from Queue import Queue


NUM_PRESPAWNED_PROCESSES = 1


_prespawned = Queue(NUM_PRESPAWNED_PROCESSES)
_thread = None
_terminated = False


def spawn(args, env_additions=None):
    '''
    Spawns a new autotest (reusing an prespawned process if available).

    @param args: A list of arguments (sys.argv)
    @param env_additions: Items to add to the current environment
    '''
    new_env = dict(os.environ)
    if env_additions:
        new_env.update(env_additions)

    process = _prespawned.get()
    # Write the environment and argv to the process's stdin; it will launch
    # autotest once these are received.
    pickle.dump((new_env, args), process.stdin, protocol=2)
    process.stdin.close()
    return process


def start():
    '''
    Starts a thread to pre-spawn autotests.
    '''
    def run():
        while not _terminated:
            process = subprocess.Popen(
                ['python', '-u', os.path.realpath(__file__),
                 '--prespawn_autotest'],
                cwd=os.path.dirname(os.path.realpath(__file__)),
                stdin=subprocess.PIPE)
            logging.debug('Pre-spawned an autotest process %d', process.pid)
            _prespawned.put(process)

        # Let stop() know that we are done
        _prespawned.put(None)

    global _thread  # pylint: disable=W0603
    if not _thread:
        _thread = threading.Thread(target=run)
        _thread.start()


def stop():
    '''
    Stops the pre-spawn thread gracefully.
    '''
    global _thread
    if not _thread:
        # Never started
        return

    global _terminated  # pylint: disable=W0603
    _terminated = True
    # Wait for any existing prespawned processes.
    while True:
        process = _prespawned.get()
        if not process:
            break
        # Send a 'None' environment and arg list to tell the prespawner
        # processes to exit.
        pickle.dump((None, None), process.stdin, protocol=2)
        process.stdin.close()
        process.wait()
    _thread = None
