# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module provides some utils for unit tests."""

import os
import sys


def set_paths_for_tests():
    """Set the project path and autotest input utility path for test modules."""
    pwd = os.getcwd()
    project = 'firmware_TouchpadMTB'
    if os.path.basename(pwd) != project:
        msg = 'Error: execute the unittests in the directory of %s!'
        print msg % project
        sys.exit(-1)
    # Append the project path
    sys.path.append(pwd)
    # Append the autotest input utility path
    sys.path.append(os.path.join(pwd, '../../bin/input/'))


set_paths_for_tests()
