#!/usr/bin/python -u
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Check an autotest control file for required variables.

This wrapper is invoked through autotest's PRESUBMIT.cfg for every commit
that edits a control file.
"""


import glob, os, re, subprocess
import common
from autotest_lib.client.common_lib import control_data
from autotest_lib.server.cros.dynamic_suite import reporting_utils


class ControlFileCheckerError(Exception):
    """Raised when a necessary condition of this checker isn't satisfied."""


def IsInChroot():
    """Return boolean indicating if we are running in the chroot."""
    return os.path.exists("/etc/debian_chroot")


def CommandPrefix():
    """Return an argv list which must appear at the start of shell commands."""
    if IsInChroot():
        return []
    else:
        return ['cros_sdk', '--']


def GetOverlayPath():
    """Return the path to the chromiumos-overlay directory."""
    ourpath = os.path.abspath(__file__)
    overlay = os.path.join(os.path.dirname(ourpath),
                           "../../../../chromiumos-overlay/")
    return os.path.normpath(overlay)


def GetAutotestTestPackages():
    """Return a list of ebuilds which should be checked for test existance."""
    overlay = GetOverlayPath()
    packages = glob.glob(os.path.join(overlay, "chromeos-base/autotest-*"))
    # Return the packages list with the leading overlay path removed.
    return [x[(len(overlay) + 1):] for x in packages]


def GetEqueryWrappers():
    """Return a list of all the equery variants that should be consulted."""
    # Note that we can't just glob.glob('/usr/local/bin/equery-*'), because
    # we might be running outside the chroot.
    pattern = '/usr/local/bin/equery-*'
    cmd = CommandPrefix() + ['sh', '-c', 'echo %s' % pattern]
    wrappers = subprocess.check_output(cmd).split()
    # If there was no match, we get the literal pattern string echoed back.
    if wrappers and wrappers[0] == pattern:
        wrappers = []
    return ['equery'] + wrappers


def CheckSuites(ctrl_data, test_name):
    """
    Check that any test in a SUITE is also in an ebuild.

    Throws a ControlFileCheckerError if a test within a SUITE
    does not appear in an ebuild. For purposes of this check,
    the psuedo-suite "manual" does not require a test to be
    in an ebuild.

    @param ctrl_data: The control_data object for a test.
    @param test_name: A string with the name of the test.

    @returns: None
    """
    if (hasattr(ctrl_data, 'suite') and ctrl_data.suite and
        ctrl_data.suite != 'manual'):
        # To handle the case where a developer has cros_workon'd
        # e.g. autotest-tests on one particular board, and has the
        # test listed only in the -9999 ebuild, we have to query all
        # the equery-* board-wrappers until we find one. We ALSO have
        # to check plain 'equery', to handle the case where e.g. a
        # developer who has never run setup_board, and has no
        # wrappers, is making a quick edit to some existing control
        # file already enabled in the stable ebuild.
        for equery in GetEqueryWrappers():
            cmd_args = (CommandPrefix() + [equery, '-qC', 'uses'] +
                        GetAutotestTestPackages())
            child = subprocess.Popen(cmd_args, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
            useflags = child.communicate()[0].splitlines()
            if child.returncode != 0:
                continue
            for flag in useflags:
                if flag.startswith('-') or flag.startswith('+'):
                    flag = flag[1:]
                if flag == 'tests_%s' % test_name:
                    return
        raise ControlFileCheckerError('No ebuild entry for %s' % test_name)


def main():
    """
    Checks if all control files that are a part of this commit conform to the
    ChromeOS autotest guidelines.
    """
    file_list = os.environ.get('PRESUBMIT_FILES')
    if file_list is None:
        raise ControlFileCheckerError('Expected a list of presubmit files in '
            'the PRESUBMIT_FILES environment variable.')

    for file_path in file_list.split('\n'):
        control_file = re.search(r'.*/control(?:\.\w+)?$', file_path)
        client_side = re.search(r'/client/', file_path)
        if control_file:
            ctrl_data = control_data.parse_control(control_file.group(0),
                                                   raise_warnings=True)
            test_name = os.path.basename(os.path.split(file_path)[0])
            try:
                reporting_utils.BugTemplate.validate_bug_template(
                        ctrl_data.bug_template)
            except AttributeError:
                # The control file may not have bug template defined.
                pass

            if client_side:
                CheckSuites(ctrl_data, test_name)


if __name__ == '__main__':
    main()
