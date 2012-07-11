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

    _EXPECTED = frozenset(['h1', 'h2'])


    def setUp(self):
        super(HostLockManagerTest, self).setUp()
        self.afe = self.mox.CreateMock(frontend.AFE)
        self.manager = host_lock_manager.HostLockManager(self.afe)
        self.manager.prime(self._EXPECTED)


    def testPrime(self):
        """Test that expected hosts are managed after prime() is called."""
        self.assertEquals(self._EXPECTED, self.manager._hosts)


    def testReprimeRaises(self):
        """Test that prime() can be called once and only once."""
        self.assertRaises(error.HostLockManagerReuse,
                          self.manager.prime, ['other'])


    def testLockUnlock(self):
        """Test that lock()/unlock() touch all prime()d hosts."""
        self.afe.run('modify_hosts',
                     host_filter_data=mox.ContainsKeyValue('hostname__in',
                                                           self._EXPECTED),
                     update_data=mox.ContainsKeyValue('locked',
                                                      True)).InAnyOrder()
        self.afe.run('modify_hosts',
                     host_filter_data=mox.ContainsKeyValue('hostname__in',
                                                           self._EXPECTED),
                     update_data=mox.ContainsKeyValue('locked',
                                                      False)).InAnyOrder()
        self.mox.ReplayAll()
        self.manager.lock()
        self.manager.unlock()


    def testDestructorUnlocks(self):
        """Test that failing to unlock manually calls it automatically."""
        local_manager = host_lock_manager.HostLockManager(self.afe)
        local_manager.prime(self._EXPECTED)
        self.afe.run('modify_hosts',
                     host_filter_data=mox.ContainsKeyValue('hostname__in',
                                                           self._EXPECTED),
                     update_data=mox.ContainsKeyValue('locked',
                                                      True)).InAnyOrder()
        self.afe.run('modify_hosts',
                     host_filter_data=mox.ContainsKeyValue('hostname__in',
                                                           self._EXPECTED),
                     update_data=mox.ContainsKeyValue('locked',
                                                      False)).InAnyOrder()
        self.mox.ReplayAll()
        local_manager.lock()
