#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for server/cros/dynamic_suite/tools.py."""

import logging
import mox
import unittest

from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.server.cros.dynamic_suite import tools


class DynamicSuiteToolsTest(mox.MoxTestBase):
    """Unit tests for dynamic_suite tools module methods."""


    def testInjectVars(self):
        """Should inject dict of varibles into provided strings."""
        def find_all_in(d, s):
            """Returns true if all key-value pairs in |d| are printed in |s|."""
            for k, v in d.iteritems():
                if isinstance(v, str):
                    if "%s='%s'\n" % (k, v) not in s:
                        return False
                else:
                    if "%s=%r\n" % (k, v) not in s:
                        return False
            return True

        v = {'v1': 'one', 'v2': 'two', 'v3': None, 'v4': False, 'v5': 5}
        self.assertTrue(find_all_in(v, tools.inject_vars(v, '')))
        self.assertTrue(find_all_in(v, tools.inject_vars(v, 'ctrl')))
