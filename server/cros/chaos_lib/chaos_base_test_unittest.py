#!/usr/bin/python
#
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for server/cros/chaos_lib/chaos_base_test.py."""

""" To run this test, from the chroot:
    $ ~/src/third_party/autotest/files/utils/unittest_suite.py
      server.cros.chaos_lib.chaos_base_test_unittest --debug
"""

import mox

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.chaos_ap_configurators import \
    ap_configurator_config
from autotest_lib.server.cros.chaos_lib import chaos_base_test


class WiFiChaosConnectionTestTest(mox.MoxTestBase):
    """Unit tests for chaos_base_test.WiFiChaosConnectionTestTest."""


    class MockBaseClass(chaos_base_test.WiFiChaosConnectionTest):
        """Mocks class of WiFiChaosConnectionTest."""


        # Mock out real objects in the base class __init__().
        def __init__(self, mox_obj):
            self.host = mox_obj.CreateMockAnything()
            self.connector = mox_obj.CreateMockAnything()
            self.disconnector = mox_obj.CreateMockAnything()
            self.outputdir = None
            self.error_list = []
            self.ap_config = ap_configurator_config.APConfiguratorConfig()


    def setUp(self):
        """Default test setup."""
        super(WiFiChaosConnectionTestTest, self).setUp()
        self.helper = self.MockBaseClass(self.mox)
        self.ap_config = ap_configurator_config.APConfiguratorConfig()


    def _setup_mode_test(self):
        #self.helper.ap_config.mode_n = self.ap_config.MODE_N
        self.mock_ap = self.mox.CreateMockAnything()


    def testGetModeType_ReturnsNon80211n(self):
        """Returns a non-802.11n mode on a given band."""
        self._setup_mode_test()
        modes = [{'band': self.ap_config.BAND_2GHZ,
                  'modes': [self.ap_config.MODE_G]}]

        self.mock_ap.get_supported_modes().AndReturn(modes)
        self.mox.ReplayAll()
        actual = self.helper._get_mode_type(self.mock_ap,
                                            self.ap_config.BAND_2GHZ)
        self.assertEquals(self.ap_config.MODE_G, actual)


    def testGetModeType_ReturnsNoneForBandMismatch(self):
        """Returns None if AP does not support the given band."""
        self._setup_mode_test()
        modes = [{'band': self.ap_config.BAND_2GHZ,
                  'modes': [self.ap_config.MODE_G]}]

        self.mock_ap.get_supported_modes().AndReturn(modes)
        self.mox.ReplayAll()
        actual = self.helper._get_mode_type(self.mock_ap,
                                            self.ap_config.BAND_5GHZ)
        self.assertEquals(None, actual)


    def testGetModeType_ReturnsNoneFor80211n(self):
        """Returns None if AP only supports 802.11n on the given band."""
        self._setup_mode_test()
        modes = [{'band': self.ap_config.BAND_2GHZ,
                  'modes': [self.ap_config.MODE_N]}]

        self.mock_ap.get_supported_modes().AndReturn(modes)
        self.mox.ReplayAll()
        actual = self.helper._get_mode_type(self.mock_ap,
                                            self.ap_config.BAND_2GHZ)
        self.assertEquals(None, actual)


    def testCheckTestPass(self):
        """Verify no exception is thrown when error_list is empty."""
        try:
            self.helper.check_test_error()
        except (error.TestFail, error.TestError) as e:
            self.fail('Should NOT raise an error here! %r' % e)


    def testCheckTestFail(self):
        """Verify TestFail is raised if error_list contains a failure."""
        ap_info = {'failed_iterations': [{'error': 'Failed to connect to blah',
                                          'try': 0}]}
        self.helper.error_list = [ap_info]
        self.assertRaises(error.TestFail, self.helper.check_test_error)


    def testCheckTestError(self):
        """Verify TestError is raised if error_list contains a config error."""
        ap_info = {'failed_iterations':
                   [{'error': self.helper.FAILED_CONFIG_MSG,
                     'try': 0}]}
        self.helper.error_list = [ap_info]
        self.assertRaises(error.TestError, self.helper.check_test_error)
