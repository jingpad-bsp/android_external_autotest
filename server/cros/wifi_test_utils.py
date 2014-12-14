# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.common_lib import error


def get_install_path(host, filename):
    """
    Checks if a file exists on a remote machine in one of several paths.

    @param host Host object representing the remote machine.
    @param filename String name of the file to check for existence.
    @return String full path of installed file, or None if not found.

    """
    PATHS = ['/bin',
             '/sbin',
             '/system/bin',
             '/usr/bin',
             '/usr/sbin',
             '/usr/local/bin',
             '/usr/local/sbin']
    glob_list = [os.path.join(path, filename) for path in PATHS]
    # Some hosts have poor support for which.  Sometimes none.
    # Others have shells that can't perform advanced globbing.
    result = host.run('ls %s 2> /dev/null' % ' '.join(glob_list),
                      ignore_status=True)
    found_path = result.stdout.split('\n')[0].strip()
    return found_path or None


def must_be_installed(host, cmd):
    """
    Asserts that cmd is installed on a remote machine at some path and raises
    an exception if this is not the case.

    @param host Host object representing the remote machine.
    @param cmd String name of the command to check for existence.
    @return String full path of cmd on success.  Error raised on failure.

    """
    if host.run('ls %s >/dev/null 2>&1' % cmd,
                ignore_status=True).exit_status == 0:
        return cmd

    # Hunt for the equivalent file in a bunch of places.
    cmd_base = os.path.basename(cmd)
    alternate_path = get_install_path(host, cmd_base)
    if alternate_path:
        return alternate_path

    raise error.TestFail('Unable to find %s on %s' % (cmd, host.ip))
