# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module provides some utils for unit tests."""

import os
import sys


def set_paths_for_tests():
    """Set the project path and autotest input utility path for test modules."""
    pwd = os.getcwd()
    project = 'firmware_TouchMTB'
    if os.path.basename(pwd) != project:
        msg = 'Error: execute the unittests in the directory of %s!'
        print msg % project
        sys.exit(-1)
    # Append the project path
    sys.path.append(pwd)
    # Append the autotest input utility path
    sys.path.append(os.path.join(pwd, '../../bin/input/'))


def get_tests_path():
    """Get the path for unit tests."""
    return os.path.join(os.getcwd(), 'tests')


def get_tests_data_path():
    """Get the data path for unit tests."""
    return os.path.join(get_tests_path(), 'data')


def get_device_description_path():
    """Get the path for device description files."""
    return os.path.join(get_tests_path(), 'device')


def parse_tests_data(filename, gesture_dir=''):
    """Parse the unit tests data."""
    import mtb
    filepath = os.path.join(get_tests_data_path(), gesture_dir, filename)
    with open(filepath) as test_file:
        return mtb.MtbParser().parse(test_file)


set_paths_for_tests()
