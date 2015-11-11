#!/usr/bin/python

"""Automatically update the afe_stable_versions table.

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

The command accepts a `--dry-run` option.  When used, the command makes
no changes, but will instead print a series of `atest` commands that
will make the required changes.  The output from the `--dry-run` option
is suitable as input to the shell.
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

# _SET_VERSION - `atest` command that will assign a specific board a
# specific stable version in the AFE.
#
# _DELETE_VERSION - `atest` command that will delete a stable version
# mapping from the AFE.
#
# _DEFAULT_BOARD - The distinguished board name used to identify a
# stable version mapping that is used for any board without an explicit
# mapping of its own.
#
_SET_VERSION = 'atest stable_version modify --board %s --version %s\n'
_DELETE_VERSION = ('atest stable_version delete --no-confirmation '
                   '--board %s\n')
_DEFAULT_BOARD = 'DEFAULT'


def _get_omaha_board(json_entry):
    """Get the board name from an 'omaha_data' entry.

    @param json_entry   Deserialized JSON object for one entry of the
                        'omaha_data' array.
    @return Returns a version number in the form R##-####.#.#.
    """
    return json_entry['board']['public_codename']


def _get_omaha_version(json_entry):
    """Get a Chrome OS version string from an 'omaha_data' entry.

    @param json_entry   Deserialized JSON object for one entry of the
                        'omaha_data' array.
    @return Returns a version number in the form R##-####.#.#.
    """
    milestone = json_entry['chrome_version'].split('.')[0]
    build = json_entry['chrome_os_version']
    return 'R%s-%s' % (milestone, build)


def _get_omaha_versions():
    """Get the current Beta versions serving on Omaha.

    Returns a dictionary mapping board names to the currently preferred
    version for the Beta channel as served by Omaha.  The board names
    are the names as known to Omaha:  If the board name in the AFE has a
    '_', the corresponding Omaha name uses a '-' instead.  The boards
    mapped may include boards not in the list of managed boards in the
    lab.

    The beta channel versions are found by searching the `_OMAHA_STATUS`
    file.  That file is calculated by GoldenEye from Omaha.  It's
    accurate, but could be out-of-date for a small time window.

    @return A dictionary mapping Omaha boards to Beta versions.
    """
    sp = subprocess.Popen(['gsutil', 'cat', _OMAHA_STATUS],
                          stdout=subprocess.PIPE)
    omaha_status = json.load(sp.stdout)
    return {_get_omaha_board(e): _get_omaha_version(e)
                for e in omaha_status['omaha_data']
                if e['channel'] == 'beta'}


def _get_upgrade_versions(afe_versions, omaha_versions, boards):
    """Get the new stable versions to which we should update.

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


def _set_stable_version(afe, dry_run, board, version):
    """Call the AFE to change a stable version mapping.

    Setting the mapping for the distinguished board name
    `_DEFAULT_BOARD` will change the default mapping for any board
    that doesn't have its own mapping.

    @param afe          AFE object for RPC calls.
    @param dry_run      If true, make no changes, but report what would
                        be done on stdout.
    @param board        Update the mapping for this board.
    @param version      Update the board to this version.
    """
    if dry_run:
        sys.stdout.write(_SET_VERSION % (board, version))
    else:
        afe.run('set_stable_version', board=board, version=version)


def _delete_stable_version(afe, dry_run, board):
    """Call the AFE to delete a stable version mapping.

    Deleting a mapping causes the board to revert to the current default
    mapping in the AFE.

    @param afe          AFE object for RPC calls.
    @param dry_run      If true, make no changes, but report what would
                        be done on stdout.
    @param board        Delete the mapping for this board.
    """
    assert board != _DEFAULT_BOARD
    if dry_run:
        sys.stdout.write(_DELETE_VERSION % board)
    else:
        afe.run('delete_stable_version', board=board)


def _apply_upgrades(afe, dry_run, afe_versions,
                    upgrade_versions, new_default):
    """Change stable version mappings in the AFE.

    Update the `afe_stable_versions` database table to have the new
    settings indicated by `upgrade_versions` and `new_default`.  Order
    the changes so that at any moment, every board is mapped either
    according to the old or the new mapping.

    @param afe                  AFE object for RPC calls.
    @param dry_run              If true, make no changes, but report
                                what would be done on stdout.
    @param afe_versions         The current board->version mappings in
                                the AFE.
    @param upgrade_versions     The current board->version mappings from
                                Omaha for the Beta channel.
    @param new_default          The new default build for the AFE.
    """
    old_default = afe_versions[_DEFAULT_BOARD]
    if not dry_run and new_default != old_default:
        sys.stdout.write('Default %s -> %s\n' %
                         (old_default, new_default))
        sys.stdout.write('Applying stable version changes:\n')
    # N.B. The ordering here matters:  Any board that will have a
    # non-default stable version must be updated _before_ we change the
    # default mapping, below.
    for board, build in upgrade_versions.items():
        if build == new_default:
            continue
        if board in afe_versions and build == afe_versions[board]:
            if dry_run:
                message = '# Leave board %s at %s\n'
            else:
                message = '    %-22s (no change) -> %s\n'
            sys.stdout.write(message % (board, build))
        else:
            if not dry_run:
                old_build = afe_versions.get(board, '(default)')
                sys.stdout.write('    %-22s %s -> %s\n' %
                                 (board, old_build, build))
            _set_stable_version(afe, dry_run, board, build)
    # At this point, all non-default mappings have been installed.
    # If there's a new default mapping, make that change now, and delete
    # any non-default mappings made obsolete by the update.
    if new_default != old_default:
        _set_stable_version(afe, dry_run, _DEFAULT_BOARD, new_default)
    for board, build in upgrade_versions.items():
        if board in afe_versions and build == new_default:
            if not dry_run:
                sys.stdout.write('    %-22s %s -> (default)\n' %
                                 (board, afe_versions[board]))
            _delete_stable_version(afe, dry_run, board)


def _parse_command_line(argv):
    """Parse the command line arguments.

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
    parser.add_argument('-n', '--dry-run', action='store_true',
                        help='print changes without executing them')
    return parser.parse_args(argv[1:])


def main(argv):
    """Standard main routine.

    @param argv  Command line arguments including `sys.argv[0]`.
    """
    arguments = _parse_command_line(argv)
    afe = frontend_wrappers.RetryingAFE(server=None)
    # The 'get_all_stable_versions' RPC returns a dictionary mapping
    # `_DEFAULT_BOARD` to the current default version, plus a set of
    # non-default board -> version mappings.
    afe_versions = afe.run('get_all_stable_versions')
    upgrade_versions, new_default = (
        _get_upgrade_versions(afe_versions,
                              _get_omaha_versions(),
                              lab_inventory.get_managed_boards(afe)))
    _apply_upgrades(afe, arguments.dry_run, afe_versions,
                    upgrade_versions, new_default)


if __name__ == '__main__':
    main(sys.argv)
