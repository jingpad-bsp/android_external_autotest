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
    """`argparse.ArgumentParser` extended with boolean option pairs."""

    def add_boolean_argument(self, name, default, **kwargs):
        """Add a pair of argument flags for a boolean option.

        This add a pair of options, named `--<name>` and `--no<name>`.
        The actions of the two options are 'store_true' and
        'store_false', respectively, with the destination `<name>`.

        If neither option is present on the command line, the default
        value for destination `<name>` is given by `default`.

        The given `kwargs` may be any arguments accepted by
        `ArgumentParser.add_argument()`, except for `action` and `dest`.

        @param name     The name of the boolean argument, used to
                        construct the option names and destination field
                        name.
        @param default  Default setting for the option when not present
                        on the command line.
        """
        exclusion_group = self.add_mutually_exclusive_group()
        exclusion_group.add_argument('--%s' % name, action='store_true',
                                     dest=name, **kwargs)
        exclusion_group.add_argument('--no%s' % name, action='store_false',
                                     dest=name, **kwargs)
        self.set_defaults(**{name: bool(default)})


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


def _add_upload_option(parser, default):
    """Add a boolean option pair for uploading logs.

    @param parser   _ArgumentParser instance.
    @param default  Default option value.
    """
    parser.add_boolean_argument('upload', default=default,
                                help='whether to upload logs to GS bucket')


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
    _add_upload_option(parser, default=full_deploy)

    arguments = parser.parse_args(argv[1:])
    arguments.full_deploy = full_deploy
    return arguments
