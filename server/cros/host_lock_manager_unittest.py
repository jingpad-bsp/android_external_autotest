#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for server/cros/host_lock_manager.py."""

import logging
import mox
import shutil
import unittest

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros import host_lock_manager
from autotest_lib.server import frontend


class HostLockManagerTest(mox.MoxTestBase):
    """Unit tests for host_lock_manager.HostLockManager.
    """

    _EXPECTED = ['h1', 'h2']


    def setUp(self):
        super(HostLockManagerTest, self).setUp()
        self.afe = self.mox.CreateMock(frontend.AFE)
        self.manager = host_lock_manager.HostLockManager(self.afe)


    def testAddSemantics(self):
        """Test that expected hosts are managed after add() is called."""
        self.manager.add(self._EXPECTED[1:])
        self.assertEquals(self._EXPECTED[1:], sorted(self.manager._hosts))
        self.manager.add(self._EXPECTED)
        self.assertEquals(sorted(self._EXPECTED), sorted(self.manager._hosts))


    def testLockUnlock(self):
        """Test that lock()/unlock() touch all add()d hosts."""
        self.manager.add(self._EXPECTED)
        self.afe.run('modify_hosts',
                     host_filter_data=mox.ContainsKeyValue(
                         'hostname__in', mox.SameElementsAs(self._EXPECTED)),
                     update_data=mox.ContainsKeyValue('locked',
                                                      True)).InAnyOrder()
        self.afe.run('modify_hosts',
                     host_filter_data=mox.ContainsKeyValue(
                         'hostname__in', mox.SameElementsAs(self._EXPECTED)),
                     update_data=mox.ContainsKeyValue('locked',
                                                      False)).InAnyOrder()
        self.mox.ReplayAll()
        self.manager.lock()
        self.manager.unlock()


    def testDestructorUnlocks(self):
        """Test that failing to unlock manually calls it automatically."""
        self.afe.run('modify_hosts',
                     host_filter_data=mox.ContainsKeyValue(
                         'hostname__in', mox.SameElementsAs(self._EXPECTED)),
                     update_data=mox.ContainsKeyValue('locked',
                                                      True)).InAnyOrder()
        self.afe.run('modify_hosts',
                     host_filter_data=mox.ContainsKeyValue(
                         'hostname__in', mox.SameElementsAs(self._EXPECTED)),
                     update_data=mox.ContainsKeyValue('locked',
                                                      False)).InAnyOrder()
        local_manager = host_lock_manager.HostLockManager(self.afe)
        local_manager.add(self._EXPECTED)
        self.mox.ReplayAll()
        local_manager.lock()
