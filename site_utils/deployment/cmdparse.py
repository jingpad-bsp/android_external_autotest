# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Command-line parsing for the DUT deployment tool.

This contains parsing for both the `repair_test` and `deployment_test`
commands.  The syntax for both commands is identical, the differences in
the two commands are primarily in slightly different defaults.

This module exports a single function, `parse_command()`.  This function
parses a command line and returns an `argparse.Namespace` object with
the result.  That `Namespace` object contains the following fields:
    `web`:  Server name (or URL) for the AFE RPC service.
    `logdir`:  The directory where logs are to be stored.
    `build`:  A build version string (in the form 'R66-10447.0.0').
        This version will be assigned as the repair image for the DUTs.
    `noinstall`:  This is a debug option.  When true, skips Servo setup
        and testing, and installation of both firmware and test images
        on the DUT.  This option is only useful as a way to quickly test
        certain parts of the script.
    `nostage`:  When true, skips Servo setup and and testing.  This can
        be used to speed up operations when the USB stick for the servo
        is known to already have the proper image installed.
    `nostable`:  This is a debug option.  When true, skips applying any
        changes to the repair image for the DUTs.
    `board`:  Specifies the board to be used for all DUTs.
    `hostname_file`:  Name of a file in CSV format with information
        about the hosts and servos to be deployed/repaired.
    `hostnames`:  List of host names.
    `upload`:  After the command completes, logs will be uploaded to
        googlestorage if this is true.
    `full_deploy`:  If this is true, the deployment process will include
        the steps to install dev-signed RO firmware on a writable
        device.
"""

import argparse
import os


class _ArgumentParser(argparse.ArgumentParser):
    """ArgumentParser extended with boolean option pairs."""

    # Arguments required when adding an option pair.
    _REQUIRED_PAIR_ARGS = {'dest', 'default'}

    def add_argument_pair(self, yes_flags, no_flags, **kwargs):
        """Add a pair of argument flags for a boolean option.

        @param yes_flags  Iterable of flags to turn option on.
                          May also be a single string.
        @param no_flags   Iterable of flags to turn option off.
                          May also be a single string.
        @param *kwargs    Other arguments to pass to add_argument()
        """
        missing_args = self._REQUIRED_PAIR_ARGS - set(kwargs)
        if missing_args:
            raise ValueError("Argument pair must have explicit %s"
                             % (', '.join(missing_args),))

        if isinstance(yes_flags, (str, unicode)):
            yes_flags = [yes_flags]
        if isinstance(no_flags, (str, unicode)):
            no_flags = [no_flags]

        self.add_argument(*yes_flags, action='store_true', **kwargs)
        self.add_argument(*no_flags, action='store_false', **kwargs)


def _make_common_parser(command_name):
    """Create argument parser for common arguments.

    @param command_name The command name.
    @return ArgumentParser instance.
    """
    parser = _ArgumentParser(
            prog=command_name,
            description='Install a test image on newly deployed DUTs')
    # frontend.AFE(server=None) will use the default web server,
    # so default for --web is `None`.
    parser.add_argument('-w', '--web', metavar='SERVER', default=None,
                        help='specify web server')
    parser.add_argument('-d', '--dir', dest='logdir',
                        help='directory for logs')
    parser.add_argument('-i', '--build',
                        help='select stable test build version')
    parser.add_argument('-n', '--noinstall', action='store_true',
                        help='skip install (for script testing)')
    parser.add_argument('-s', '--nostage', action='store_true',
                        help='skip staging test image (for script testing)')
    parser.add_argument('-t', '--nostable', action='store_true',
                        help='skip changing stable test image '
                             '(for script testing)')
    parser.add_argument('-f', '--hostname_file',
                        help='CSV file that contains a list of hostnames and '
                             'their details to install with.')
    parser.add_argument('board', nargs='?', metavar='BOARD',
                        help='board for DUTs to be installed')
    parser.add_argument('hostnames', nargs='*', metavar='HOSTNAME',
                        help='host names of DUTs to be installed')
    return parser


def _add_upload_argument_pair(parser, default):
    """Add an option pair for uploading logs.

    @param parser   _ArgumentParser instance.
    @param default  Default option value.
    """
    parser.add_argument_pair('--upload', '--noupload', dest='upload',
                             default=default,
                             help='whether to upload logs to GS bucket',)


def parse_command(argv, full_deploy):
    """Get arguments for install from `argv` or the user.

    Create an argument parser for this command's syntax, parse the
    command line, and return an `argparse.Namespace` object with the
    results.

    @param argv         Standard command line argument vector;
                        argv[0] is assumed to be the command name.
    @param full_deploy  Whether this is for full deployment or
                        repair.

    @return Result, as returned by ArgumentParser.parse_args().
    """
    command_name = os.path.basename(argv[0])
    parser = _make_common_parser(command_name)
    _add_upload_argument_pair(parser, default=full_deploy)

    arguments = parser.parse_args(argv[1:])
    arguments.full_deploy = full_deploy
    return arguments
