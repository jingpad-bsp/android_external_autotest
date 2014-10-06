#!/usr/bin/env python
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Common functionality used by multiple scripts in the perf dashboard.
"""

import os, sys
dirname = os.path.dirname(sys.modules[__name__].__file__)
autotest_dir = os.path.abspath(os.path.join(dirname, '..', '..'))
client_dir = os.path.join(autotest_dir, 'client')
sys.path.insert(0, client_dir)
import setup_modules
sys.path.pop(0)
setup_modules.setup(base_path=autotest_dir, root_module_name='autotest_lib')


def die_if_already_running(pid_file, logging):
    """Dies if another instance of a given script's pid is already running.

    @param pid_file: A string name for a file containing the pid of a running
        (or possibly not running) script.
    @param logging: A logging.Logger object.

    If the specified file contains a pid that is no longer running, or if the
    specified file doesn't exist, then writes the currently-running pid to that
    file.
    """
    if os.path.isfile(pid_file):
        existing_pid = None
        with open(pid_file, 'r') as fp:
            existing_pid = fp.read() or 'None'  # Force 'None' if empty file.
        if os.path.isdir('/proc/' + existing_pid):
            logging.error('Script already running with pid %s.', existing_pid)
            sys.exit(1)
    with open(pid_file, 'w') as fp:
        fp.write(str(os.getpid()))
