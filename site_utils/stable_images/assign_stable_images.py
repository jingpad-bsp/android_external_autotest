#!/usr/bin/python
# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Automatically update the afe_stable_versions table.

This command updates the stable repair version for selected boards
in the lab.  For each board, if the version that Omaha is serving
on the Beta channel for the board is more recent than the current
stable version in the AFE database, then the AFE is updated to use
the version on Omaha.

The upgrade process is applied to every "managed board" in the test
lab.  Generally, a managed board is a board with both spare and
critical scheduling pools.

See `autotest_lib.site_utils.lab_inventory` for the full definition
of "managed board".

The command supports a `--dry-run` option that reports changes that
would be made, without making the actual RPC calls to change the
database.

"""

import argparse
import json
import subprocess
import sys

import common
from autotest_lib.client.common_lib import utils
from autotest_lib.server.cros.dynamic_suite import frontend_wrappers
from autotest_lib.site_utils import lab_inventory


# _OMAHA_STATUS - URI of a file in GoogleStorage with a JSON object
# summarizing all versions currently being served by Omaha.
#
# The principle data is in an array named 'omaha_data'.  Each entry
# in the array contains information relevant to one image being
# served by Omaha, including the following information:
#   * The board name of the product, as known to Omaha.
#   * The channel associated with the image.
#   * The Chrome and Chrome OS version strings for the image
#     being served.
#
_OMAHA_STATUS = 'gs://chromeos-build-release-console/omaha_status.json'


# _DEFAULT_BOARD - The distinguished board name used to identify a
# stable version mapping that is used for any board without an explicit
# mapping of its own.
#
# _DEFAULT_VERSION_TAG - A string used to signify that there is no
# mapping for a board, in other words, the board is mapped to the
# default version.
#
_DEFAULT_BOARD = 'DEFAULT'
_DEFAULT_VERSION_TAG = '(default)'


class _VersionUpdater(object):
    """
    Class to report and apply version changes.

    This class is responsible for the low-level logic of applying
    version upgrades and reporting them as command output.

    This class exists to solve two problems:
     1. To distinguish "normal" vs. "dry-run" modes.  Each mode has a
        subclass; methods that perform actual AFE updates are
        implemented for the normal mode subclass only.
     2. To provide hooks for unit tests.  The unit tests override both
        the reporting and modification behaviors, in order to test the
        higher level logic that decides what changes are needed.

    Methods meant merely to report changes to command output have names
    starting with "report" or "_report".  Methods that are meant to
    change the AFE in normal mode have names starting with "_do"
    """

    def __init__(self, afe):
        self._afe = afe
        self._version_map = None

    def select_version_map(self, image_type):
        """
        Select an AFE version map object based on `image_type`.

        This creates and remembers an AFE version mapper object to be
        used for making changes in normal mode.

        @param image_type   Image type parameter for the version mapper
                            object.
        @returns The full set of mappings for the image type.
        """
        self._version_map = self._afe.get_stable_version_map(image_type)
        return self._version_map.get_all_versions()

    def announce(self):
        """Announce the start of processing to the user."""
        pass

    def report(self, message):
        """
        Report a pre-formatted message for the user.

        The message is printed to stdout, followed by a newline.

        @param message The message to be provided to the user.
        """
        print message

    def report_default_changed(self, old_default, new_default):
        """
        Report that the default version mapping is changing.

        This merely reports a text description of the pending change
        without executing it.

        @param old_default  The original default version.
        @param new_default  The new default version to be applied.
        """
        self.report('Default %s -> %s' % (old_default, new_default))

    def _report_board_changed(self, board, old_version, new_version):
        """
        Report a change in one board's assigned version mapping.

        This merely reports a text description of the pending change
        without executing it.

        @param board        The board with the changing version.
        @param old_version  The original version mapped to the board.
        @param new_version  The new version to be applied to the board.
        """
        template = '    %-22s %s -> %s'
        self.report(template % (board, old_version, new_version))

    def report_board_unchanged(self, board, old_version):
        """
        Report that a board's version mapping is unchanged.

        This reports that a board has a non-default mapping that will be
        unchanged.

        @param board        The board that is not changing.
        @param old_version  The board's version mapping.
        """
        self._report_board_changed(board, '(no change)', old_version)

    def _do_set_mapping(self, board, new_version):
        """
        Change one board's assigned version mapping.

        @param board        The board with the changing version.
        @param new_version  The new version to be applied to the board.
        """
        pass

    def _do_delete_mapping(self, board):
        """
        Delete one board's assigned version mapping.

        @param board        The board with the version to be deleted.
        """
        pass

    def set_mapping(self, board, old_version, new_version):
        """
        Change and report a board version mapping.

        @param board        The board with the changing version.
        @param old_version  The original version mapped to the board.
        @param new_version  The new version to be applied to the board.
        """
        self._report_board_changed(board, old_version, new_version)
        self._do_set_mapping(board, new_version)

    def upgrade_default(self, new_default):
        """
        Apply a default version change.

        @param new_default  The new default version to be applied.
        """
        self._do_set_mapping(_DEFAULT_BOARD, new_default)

    def delete_mapping(self, board, old_version):
        """
        Delete a board version mapping, and report the change.

        @param board        The board with the version to be deleted.
        @param old_version  The board's verson prior to deletion.
        """
        assert board != _DEFAULT_BOARD
        self._report_board_changed(board,
                                   old_version,
                                   _DEFAULT_VERSION_TAG)
        self._do_delete_mapping(board)


class _DryRunUpdater(_VersionUpdater):
    """Code for handling --dry-run execution."""

    def announce(self):
        self.report('Dry run:  no changes will be made.')


class _NormalModeUpdater(_VersionUpdater):
    """Code for handling normal execution."""

    def _do_set_mapping(self, board, new_version):
        self._version_map.set_version(board, new_version)

    def _do_delete_mapping(self, board):
        self._version_map.delete_version(board)


def _read_gs_json_data(gs_uri):
    """
    Read and parse a JSON file from googlestorage.

    This is a wrapper around `gsutil cat` for the specified URI.
    The standard output of the command is parsed as JSON, and the
    resulting object returned.

    @return A JSON object parsed from `gs_uri`.
    """
    sp = subprocess.Popen(['gsutil', 'cat', gs_uri],
                          stdout=subprocess.PIPE)
    try:
        json_object = json.load(sp.stdout)
    finally:
        sp.stdout.close()
        sp.wait()
    return json_object


def _make_omaha_versions(omaha_status):
    """
    Convert parsed omaha versions data to a versions mapping.

    Returns a dictionary mapping board names to the currently preferred
    version for the Beta channel as served by Omaha.  The mappings are
    provided by settings in the JSON object `omaha_status`.

    The board names are the names as known to Omaha:  If the board name
    in the AFE contains '_', the corresponding Omaha name uses '-'
    instead.  The boards mapped may include boards not in the list of
    managed boards in the lab.

    @return A dictionary mapping Omaha boards to Beta versions.
    """
    def _entry_valid(json_entry):
        return json_entry['channel'] == 'beta'

    def _get_omaha_data(json_entry):
        board = json_entry['board']['public_codename']
        milestone = json_entry['milestone']
        build = json_entry['chrome_os_version']
        version = 'R%d-%s' % (milestone, build)
        return (board, version)

    return dict([_get_omaha_data(e) for e in omaha_status['omaha_data']
                    if _entry_valid(e)])


def _get_upgrade_versions(afe_versions, omaha_versions, boards):
    """
    Get the new stable versions to which we should update.

    The new versions are returned as a tuple of a dictionary mapping
    board names to versions, plus a new default board setting.  The
    new default is determined as the most commonly used version
    across the given boards.

    The new dictionary will have a mapping for every board in `boards`.
    That mapping will be taken from `afe_versions`, unless the board has
    a mapping in `omaha_versions` _and_ the omaha version is more recent
    than the AFE version.

    @param afe_versions     The current board->version mappings in the
                            AFE.
    @param omaha_versions   The current board->version mappings from
                            Omaha for the Beta channel.
    @param boards           Set of boards to be upgraded.
    @return Tuple of (mapping, default) where mapping is a dictionary
            mapping boards to versions, and default is a version string.
    """
    upgrade_versions = {}
    version_counts = {}
    afe_default = afe_versions[_DEFAULT_BOARD]
    for board in boards:
        version = afe_versions.get(board, afe_default)
        omaha_version = omaha_versions.get(board.replace('_', '-'))
        if (omaha_version is not None and
                utils.compare_versions(version, omaha_version) < 0):
            version = omaha_version
        upgrade_versions[board] = version
        version_counts.setdefault(version, 0)
        version_counts[version] += 1
    return (upgrade_versions,
            max(version_counts.items(), key=lambda x: x[1])[0])


def _apply_cros_upgrades(updater, old_versions, new_versions,
                         new_default):
    """
    Change CrOS stable version mappings in the AFE.

    The input `old_versions` dictionary represents the content of the
    `afe_stable_versions` database table; it contains mappings for a
    default version, plus exceptions for boards with non-default
    mappings.

    The `new_versions` dictionary contains a mapping for every board,
    including boards that will be mapped to the new default version.

    This function applies the AFE changes necessary to produce the new
    AFE mappings indicated by `new_versions` and `new_default`.  The
    changes are ordered so that at any moment, every board is mapped
    either according to the old or the new mapping.

    @param updater        Instance of _VersionUpdater responsible for
                          making the actual database changes.
    @param old_versions   The current board->version mappings in the
                          AFE.
    @param new_versions   New board->version mappings obtained by
                          applying Beta channel upgrades from Omaha.
    @param new_default    The new default build for the AFE.
    """
    old_default = old_versions[_DEFAULT_BOARD]
    if old_default != new_default:
        updater.report_default_changed(old_default, new_default)
    updater.report('Applying stable version changes:')
    default_count = 0
    for board, new_build in new_versions.items():
        if new_build == new_default:
            default_count += 1
        elif board in old_versions and new_build == old_versions[board]:
            updater.report_board_unchanged(board, new_build)
        else:
            old_build = old_versions.get(board)
            if old_build is None:
                old_build = _DEFAULT_VERSION_TAG
            updater.set_mapping(board, old_build, new_build)
    if old_default != new_default:
        updater.upgrade_default(new_default)
    for board, new_build in new_versions.items():
        if new_build == new_default and board in old_versions:
            updater.delete_mapping(board, old_versions[board])
    updater.report('%d boards now use the default mapping' %
                   default_count)


def _parse_command_line(argv):
    """
    Parse the command line arguments.

    Create an argument parser for this command's syntax, parse the
    command line, and return the result of the ArgumentParser
    parse_args() method.

    @param argv Standard command line argument vector; argv[0] is
                assumed to be the command name.
    @return Result returned by ArgumentParser.parse_args().

    """
    parser = argparse.ArgumentParser(
            prog=argv[0],
            description='Update the stable repair version for all '
                        'boards')
    parser.add_argument('-n', '--dry-run', dest='updater_mode',
                        action='store_const', const=_DryRunUpdater,
                        help='print changes without executing them')
    parser.add_argument('extra_boards', nargs='*', metavar='BOARD',
                        help='Names of additional boards to be updated.')
    arguments = parser.parse_args(argv[1:])
    if not arguments.updater_mode:
        arguments.updater_mode = _NormalModeUpdater
    return arguments


def main(argv):
    """
    Standard main routine.

    @param argv  Command line arguments including `sys.argv[0]`.
    """
    arguments = _parse_command_line(argv)
    afe = frontend_wrappers.RetryingAFE(server=None)
    updater = arguments.updater_mode(afe)
    updater.announce()
    boards = (set(arguments.extra_boards) |
              lab_inventory.get_managed_boards(afe))

    afe_versions = updater.select_version_map(afe.CROS_IMAGE_TYPE)
    omaha_versions = _make_omaha_versions(
            _read_gs_json_data(_OMAHA_STATUS))
    upgrade_versions, new_default = (
        _get_upgrade_versions(afe_versions, omaha_versions, boards))
    _apply_cros_upgrades(updater, afe_versions,
                         upgrade_versions, new_default)


if __name__ == '__main__':
    main(sys.argv)
