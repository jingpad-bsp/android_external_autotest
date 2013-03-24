#!/usr/bin/python -u
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Check an autotest control file for required variables.

This wrapper is invoked through autotest's PRESUBMIT.cfg for every commit
that edits a control file.
"""


import os, re
import common
from autotest_lib.client.common_lib import control_data


class ControlFileCheckerError(Exception):
    """Raised when a necessary condition of this checker isn't satisfied."""


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
        if control_file:
            control_data.parse_control(control_file.group(0),
                                       raise_warnings=True)


if __name__ == '__main__':
    main()
