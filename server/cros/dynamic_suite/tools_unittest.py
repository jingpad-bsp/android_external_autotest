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
from autotest_lib.server.cros.dynamic_suite.fakes import FakeHost


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


    def testIncorrectlyLocked(self):
        """Should detect hosts locked by random users."""
        host = FakeHost(locked=True, locked_by='some guy')
        self.assertTrue(tools.incorrectly_locked(host))


    def testNotIncorrectlyLocked(self):
        """Should accept hosts locked by the infrastructure."""
        infra_user = 'an infra user'
        self.mox.StubOutWithMock(tools, 'infrastructure_user_list')
        tools.infrastructure_user_list().AndReturn([infra_user])
        self.mox.ReplayAll()
        host = FakeHost(locked=True, locked_by=infra_user)
        self.assertFalse(tools.incorrectly_locked(host))
