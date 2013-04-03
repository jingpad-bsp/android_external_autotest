#!/usr/bin/python
#
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for server/cros/chaos_lib/chaos_base_test.py."""

import mox

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.chaos_ap_configurators import ap_configurator
from autotest_lib.server.cros.chaos_lib import chaos_base_test


class WiFiChaosConnectionTestTest(mox.MoxTestBase):
    """Unit tests for chaos_base_test.WiFiChaosConnectionTestTest."""


    class MockBaseClass(chaos_base_test.WiFiChaosConnectionTest):
        """Mocks class of WiFiChaosConnectionTest."""


        # Mock out real objects in the base class __init__().
        def __init__(self, mox_obj):
            self.host = mox_obj.CreateMockAnything()
            self.capturer = mox_obj.CreateMockAnything()
            self.connector = mox_obj.CreateMockAnything()
            self.disconnector = mox_obj.CreateMockAnything()
            self.generic_ap = mox_obj.CreateMockAnything()
            self.outputdir = None
            self.error_list = []


    def setUp(self):
        super(WiFiChaosConnectionTestTest, self).setUp()
        self.helper = self.MockBaseClass(self.mox)
        self.base_ap = ap_configurator.APConfigurator()


    def _setup_mode_test(self):
        self.helper.generic_ap.mode_n = self.base_ap.mode_n
        self.mock_ap = self.mox.CreateMockAnything()


    def testGetModeType_ReturnsNon80211n(self):
        """Returns a non-802.11n mode on a given band."""
        self._setup_mode_test()
        modes = [{'band': self.base_ap.band_2ghz,
                  'modes': [self.base_ap.mode_g]}]

        self.mock_ap.get_supported_modes().AndReturn(modes)
        self.mox.ReplayAll()
        actual = self.helper._get_mode_type(self.mock_ap,
                                            self.base_ap.band_2ghz)
        self.assertEquals(self.base_ap.mode_g, actual)


    def testGetModeType_ReturnsNoneForBandMismatch(self):
        """Returns None if AP does not support the given band."""
        self._setup_mode_test()
        modes = [{'band': self.base_ap.band_2ghz,
                  'modes': [self.base_ap.mode_g]}]

        self.mock_ap.get_supported_modes().AndReturn(modes)
        self.mox.ReplayAll()
        actual = self.helper._get_mode_type(self.mock_ap,
                                            self.base_ap.band_5ghz)
        self.assertEquals(None, actual)


    def testGetModeType_ReturnsNoneFor80211n(self):
        """Returns None if AP only supports 802.11n on the given band."""
        self._setup_mode_test()
        modes = [{'band': self.base_ap.band_2ghz,
                  'modes': [self.base_ap.mode_n]}]

        self.mock_ap.get_supported_modes().AndReturn(modes)
        self.mox.ReplayAll()
        actual = self.helper._get_mode_type(self.mock_ap,
                                            self.base_ap.band_2ghz)
        self.assertEquals(None, actual)


    def testCheckTestError(self):
        """Tests that error is raised if error_list is non-empty."""
        # Empty error_list should NOT trigger an error.
        try:
            self.helper.check_test_error()
        except error.TestFail as e:
            self.fail('Should NOT raise an error here! %r' % e)

        self.helper.error_list = ['error']
        self.assertRaises(error.TestFail, self.helper.check_test_error)
