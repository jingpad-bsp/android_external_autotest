# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Definition of a CrOS suite in skylab.

This file is a simplicication of dynamic_suite.suite without any useless
features for skylab suite.

Suite class in this file mainly has 2 features:
    1. Integrate parameters from control file & passed in arguments.
    2. Find proper child tests for a given suite.

Use case:
    See _run_suite() in skylab_suite.run_suite_skylab.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

class Suite(object):
    """The class for a CrOS suite."""

    def __init__(self):
        self.tests = []
        self.wait = True
