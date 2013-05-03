#!/usr/bin/python
#
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for server/cros/chaos_ap_configurators/ap_batch_locker.py."""

import mox

from autotest_lib.server.cros.chaos_ap_configurators import ap_batch_locker
from autotest_lib.server.cros.chaos_ap_configurators import \
    ap_configurator_factory


class ConstructApLockersTest(mox.MoxTestBase):
    """Unit tests for ap_batch_locker.construct_ap_lockers()."""


    def setUp(self):
        """Initialize."""
        super(ConstructApLockersTest, self).setUp()
        self.mox.StubOutWithMock(ap_configurator_factory,
                                 'APConfiguratorFactory')
        self.mox.StubOutWithMock(ap_batch_locker, 'ApLocker')
        self.mock_factory = self.mox.CreateMockAnything()
        self.retries = 1


    def testConstructApLockers_withEmptyApSpec(self):
        """Tests an empty list is returned by default."""
        ap_configurator_factory.APConfiguratorFactory().AndReturn(
                self.mock_factory)
        self.mock_factory.get_ap_configurators({}).AndReturn([])
        self.mox.ReplayAll()
        actual = ap_batch_locker.construct_ap_lockers({}, self.retries)
        self.assertEquals([], actual)


    def testConstructApLockers_withValidApSpec(self):
        """Tests proper mocks are invoked with a valid ap_spec."""
        ap_spec = {'security': ''}
        mock_ap1 = 'mock_ap1'
        mock_ap2 = 'mock_ap2'
        mock_ap_list = [mock_ap1, mock_ap2]
        ap_configurator_factory.APConfiguratorFactory().AndReturn(
                self.mock_factory)
        self.mock_factory.get_ap_configurators(ap_spec).AndReturn(mock_ap_list)
        ap_batch_locker.ApLocker(mock_ap1, self.retries).AndReturn(mock_ap1)
        ap_batch_locker.ApLocker(mock_ap2, self.retries).AndReturn(mock_ap2)
        self.mox.ReplayAll()
        actual = ap_batch_locker.construct_ap_lockers(ap_spec, self.retries)
        self.assertEquals(mock_ap_list, actual)


# host name of a mock APConfigurator.
MOCK_AP = 'mock_ap'


class MockApConfigurator(object):
    """Mock of an APConfigurator object.

    @attribute host_name: a string, ap host name.
    """


    def __init__(self):
        """Initialize.

        @attribute host_name: a string, ap host name.
        """
        self.host_name = MOCK_AP


class ApBatchLockerLockApInAfeTest(mox.MoxTestBase):
    """Unit tests for ap_batch_locker.ApBatchLocker.lock_ap_in_afe()."""


    class MockApBatchLocker(ap_batch_locker.ApBatchLocker):
        """Mock of ap_batch_locker.ApBatchLocker().

        @attribute aps_to_lock: a list of ApLocker objects.
        """

        def __init__(self, mox_obj):
            """Initialize."""
            self.aps_to_lock = []
            self.manager = mox_obj.CreateMockAnything()


    def setUp(self):
        """Initialize."""
        super(ApBatchLockerLockApInAfeTest, self).setUp()
        self.mock_batch_locker = self.MockApBatchLocker(self.mox)
        self.retries = 2
        self.mock_ap_locker = None


    def _set_up_mocks(self, retries):
        """Sets up mocks.

        @param retries: an integer.
        """
        self.mock_ap_locker = ap_batch_locker.ApLocker(
                MockApConfigurator(), retries)
        self.mock_batch_locker.aps_to_lock = [self.mock_ap_locker]


    def testLockApInAfe_WithLockableAp(self):
        """Tests AP can be locked and removed from ap_list."""
        self._set_up_mocks(self.retries)
        self.mock_batch_locker.manager.lock_one_host(MOCK_AP).AndReturn(True)
        self.mox.ReplayAll()
        actual = self.mock_batch_locker.lock_ap_in_afe(self.mock_ap_locker)
        self.assertEquals(True, actual)
        self.assertEquals(False, self.mock_ap_locker.to_be_locked)


    def testLockApInAfe_WithUnlockableApAndRetriesRemaining(self):
        """Tests retries counter (of an unlockable AP) is properly deducted."""
        self._set_up_mocks(self.retries)
        expected_retries = self.retries - 1
        self.mock_batch_locker.manager.lock_one_host(MOCK_AP).AndReturn(False)
        self.mox.ReplayAll()
        actual_ret = self.mock_batch_locker.lock_ap_in_afe(self.mock_ap_locker)
        self.assertEquals(False, actual_ret)
        self.assertEquals(expected_retries, self.mock_ap_locker.retries)


    def testLockApInAfe_WithUnlockableApAndNoRetriesRemaining(self):
        """Tests removal of an unlockable AP w/ no retries remaining."""
        self.retries = 1
        expected_retries = 0
        self._set_up_mocks(self.retries)
        self.mock_batch_locker.manager.lock_one_host(MOCK_AP).AndReturn(False)
        self.mox.ReplayAll()
        actual_ret = self.mock_batch_locker.lock_ap_in_afe(self.mock_ap_locker)
        self.assertEquals(False, actual_ret)
        self.assertEquals(expected_retries, self.mock_ap_locker.retries)



class ApBatchLockerGetApBatchTest(mox.MoxTestBase):
    """Unit tests for ap_batch_locker.ApBatchLocker.get_ap_batch()."""


    class MockApBatchLocker(ap_batch_locker.ApBatchLocker):
        """Mock of ap_batch_locker.ApBatchLocker().

        @attribute aps_to_lock: a list of ApLocker objects.
        """

        def __init__(self):
            """Initialize."""
            self.aps_to_lock = []


    def setUp(self):
        """Initialize."""
        super(ApBatchLockerGetApBatchTest, self).setUp()
        self.mox.StubOutWithMock(ap_batch_locker.ApBatchLocker,
                                 'lock_ap_in_afe')
        self.mock_batch_locker = self.MockApBatchLocker()
        self.batch_size = 2
        self.retries = 2


    def testGetApBatch_WithEmptyApList(self):
        """Tests an empty list is returned by default."""
        actual = self.mock_batch_locker.get_ap_batch(self.batch_size)
        self.assertEquals([], actual)


    def testGetApBatch_WithListOfOneApAndBatchSizeOne(self):
        """Tests batch_size of 1 returns inside while loop."""
        self.batch_size = 1
        mock_ap = MockApConfigurator()
        mock_ap_locker = ap_batch_locker.ApLocker(mock_ap, self.retries)
        self.mock_batch_locker.aps_to_lock = [mock_ap_locker]
        self.mock_batch_locker.lock_ap_in_afe(mock_ap_locker).AndReturn(True)
        self.mox.ReplayAll()
        actual = self.mock_batch_locker.get_ap_batch(self.batch_size)
        self.assertEquals([mock_ap], actual)
