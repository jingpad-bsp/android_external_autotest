#!/usr/bin/python
#
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for server/cros/chaos_ap_configurators/ap_configurator_factory.py.
"""

import mox

from autotest_lib.server.cros.chaos_ap_configurators import \
    ap_configurator_config
from autotest_lib.server.cros.chaos_ap_configurators import \
    ap_configurator_factory
from autotest_lib.server.cros.chaos_ap_configurators import \
    ap_spec


class APConfiguratorFactoryTest(mox.MoxTestBase):
    """Unit tests for ap_configurator_factory.APConfiguratorFactory."""


    class MockAp(object):
        """Mock object used to test _get_aps_with_bands()."""

        def __init__(self, bands_and_channels=[], bands_and_modes=[],
                     supported_securities=[], visibility_supported=False,
                     host_name='mock_ap'):
            """Constructor.

            @param bands_and_channels: a list of dicts of strings, e.g.
                [{'band': self.ap_config.BAND_2GHZ, 'channels': [5]},
                 {'band': self.ap_config.BAND_5GHZ, 'channels': [48]}]
            @param bands_and_modes: a list of dicts of strings, e.g.
                [{'band': self.ap_config.BAND_2GHZ,
                  'modes': [self.ap_config.MODE_B]},
                 {'band': self.ap_config.BAND_5GHZ,
                  'modes': [self.ap_config.MODE_G]}]
            @param supported_securities: a list of integers.
            @param visibility_supported: a boolean
            """
            self.bands_and_channels = bands_and_channels
            self.bands_and_modes = bands_and_modes
            self.supported_securities = supported_securities
            self.visibility_supported = visibility_supported
            self.host_name = host_name
            self.channel = None


        def get_supported_bands(self):
            """@returns supported bands and channels."""
            return self.bands_and_channels


        def get_supported_modes(self):
            """@returns supported bands and modes."""
            return self.bands_and_modes


        def is_security_mode_supported(self, security):
            """Checks if security is supported.

            @param security: an integer, security method.
            @returns a boolean, True iff security is supported.
            """
            return security in self.supported_securities


        def is_visibility_supported(self):
            """Returns if visibility is supported."""
            return self.visibility_supported


        def host_name(self):
            """Returns the host name of the AP."""
            return self.host_name


        def set_using_ap_spec(self, ap_spec):
            """Sets a limited numberof setting of the AP.

            @param ap_spec: APSpec object
            """
            self.channel = ap_spec.channel


        def get_channel(self):
            """Returns the channel."""
            return self.channel


    def setUp(self):
        """Initialize."""
        super(APConfiguratorFactoryTest, self).setUp()
        self.factory = ap_configurator_factory.APConfiguratorFactory()
        # ap_config is used to fetch constants such as bands, modes, etc.
        self.ap_config = ap_configurator_config.APConfiguratorConfig()


    def testCleanUpApSpec_WithValidBandsOnly(self):
        """Test with valid bands only."""
        actual = self.factory._cleanup_ap_spec(
            'bands', [self.ap_config.BAND_2GHZ])
        self.assertEquals([self.ap_config.BAND_2GHZ], actual)


    def testCleanUpApSpec_WithInvalidBandsOnly(self):
        """Test with invalid bands only."""
        actual = self.factory._cleanup_ap_spec('bands', ['2.3GHz'])
        self.assertEquals([], actual)


    def testCleanUpApSpec_WithSomeValidBands(self):
        """Test with a mix of valid and invalid bands."""
        actual = self.factory._cleanup_ap_spec(
            'bands', ['2.5GHz', self.ap_config.BAND_5GHZ])
        self.assertEquals([self.ap_config.BAND_5GHZ], actual)


    def testCleanUpApSpec_WithValidModesOnly(self):
        """Test with valid modes only."""
        actual = self.factory._cleanup_ap_spec(
            'modes', [self.ap_config.MODE_G])
        self.assertEquals([self.ap_config.MODE_G], actual)


    def testCleanUpApSpec_WithInvalidModesOnly(self):
        """Test with invalid modes only."""
        actual = self.factory._cleanup_ap_spec('modes', [0x00110])
        self.assertEquals([], actual)


    def testCleanUpApSpec_WithSomeValidModes(self):
        """Test with a mix of valid and invalid modes."""
        expected = set([self.ap_config.MODE_A, self.ap_config.MODE_B])
        actual = self.factory._cleanup_ap_spec(
            'modes', [self.ap_config.MODE_A, self.ap_config.MODE_B, 0x00011])
        self.assertEquals(expected, set(actual))


    def testCleanUpApSpec_WithValidSecuritiesOnly(self):
        """Test with valid securities only."""
        actual = self.factory._cleanup_ap_spec(
            'securities', [self.ap_config.SECURITY_TYPE_DISABLED])
        self.assertEquals([self.ap_config.SECURITY_TYPE_DISABLED], actual)


    def testCleanUpApSpec_WithInvalidSecuritiesOnly(self):
        """Test with invalid securities only."""
        actual = self.factory._cleanup_ap_spec('securities', [4])
        self.assertEquals([], actual)


    def testCleanUpApSpec_WithSomeValidSecurities(self):
        """Test with a mix of valid and invalid securities."""
        expected = [self.ap_config.SECURITY_TYPE_WEP,
                    self.ap_config.SECURITY_TYPE_WPAPSK]
        test_securities = [-1, self.ap_config.SECURITY_TYPE_WEP,
                           self.ap_config.SECURITY_TYPE_WPAPSK]
        actual = self.factory._cleanup_ap_spec('securities', test_securities)
        self.assertEquals(expected, actual)


    def testGetApsWithBands_WithEmptyBands(self):
        """Test with empty bands and empty ap_list."""
        self.assertEquals(None, self.factory._get_aps_with_bands([], []))


    def testGetApsWithBands_WithInvalidBandsOnly(self):
        """Test with invalid bands and empty ap_list."""
        actual = self.factory._get_aps_with_bands(['invalid_band'], [])
        self.assertEquals(None, actual)

    def testGetApsWithBands_WithValidBandsAndEmptyApList(self):
        """Test with valid bands and empty ap_list."""
        actual = self.factory._get_aps_with_bands(
            [self.ap_config.BAND_5GHZ], [])
        self.assertEquals([], actual)


    def testGetApsWithBands_WithValidBandsAndApListReturnsOne(self):
        """Test with valid bands and ap_list returns a list of one."""
        # Two single-band APs.
        mock_ap1 = self.MockAp(
            bands_and_channels=[{'band': self.ap_config.BAND_2GHZ,
                                 'channels': [5]}])
        mock_ap2 = self.MockAp(
            bands_and_channels=[{'band': self.ap_config.BAND_5GHZ,
                                 'channels': [48]}])
        test_aps = [mock_ap1, mock_ap2]

        actual = self.factory._get_aps_with_bands(
            [self.ap_config.BAND_2GHZ], test_aps)
        self.assertEquals([mock_ap1], actual)

        actual = self.factory._get_aps_with_bands(
            [self.ap_config.BAND_5GHZ], test_aps)
        self.assertEquals([mock_ap2], actual)


    def testGetApsWithBands_WithValidBandsAndApListReturnsTwo(self):
        """Test with valid bands and ap_list returns a list of two."""
        mock_ap1 = self.MockAp(
            bands_and_channels=[{'band': self.ap_config.BAND_2GHZ,
                                 'channels': [5]}])
        mock_ap2 = self.MockAp(
            bands_and_channels=[{'band': self.ap_config.BAND_5GHZ,
                                 'channels': [48]}])
        # A dual-band AP.
        mock_ap3 = self.MockAp(
            bands_and_channels=[{'band': self.ap_config.BAND_2GHZ,
                                 'channels': [11]},
                                {'band': self.ap_config.BAND_5GHZ,
                                 'channels': [153]}])
        test_aps = [mock_ap1, mock_ap2, mock_ap3]
        # Find APs that supports 2.4GHz band.
        actual = self.factory._get_aps_with_bands(
            [self.ap_config.BAND_2GHZ], test_aps)
        self.assertEquals([mock_ap1, mock_ap3], actual)
        # Find APs that supports 5GHz band.
        actual = self.factory._get_aps_with_bands(
            [self.ap_config.BAND_5GHZ], test_aps)
        self.assertEquals([mock_ap2, mock_ap3], actual)
        # Find APs that supports both 2.4GHz and 5GHz bands.
        actual = self.factory._get_aps_with_bands(
            [self.ap_config.BAND_2GHZ, self.ap_config.BAND_5GHZ], test_aps)
        self.assertEquals([mock_ap3], actual)


    def testGetApsWithModes_WithEmptyModes(self):
        """Test with empty modes and empty ap_list."""
        self.assertEquals(None, self.factory._get_aps_with_modes([], []))


    def testGetApsWithModes_WithInvalidModesOnly(self):
        """Test with invalid modes and empty ap_list."""
        actual = self.factory._get_aps_with_modes(['invalid_mode'], [])
        self.assertEquals(None, actual)

    def testGetApsWithModes_WithValidModesAndEmptyApList(self):
        """Test with valid modes and empty ap_list."""
        actual = self.factory._get_aps_with_modes([self.ap_config.MODE_A], [])
        self.assertEquals([], actual)


    def testGetApsWithModes_WithValidModesAndApListReturnsOne(self):
        """Test with valid modes and ap_list."""
        # A single-band AP supporting 802.11a/b.
        mock_ap1 = self.MockAp(
            bands_and_modes=[{'band': self.ap_config.BAND_2GHZ,
                              'modes': [self.ap_config.MODE_A,
                                        self.ap_config.MODE_B]}])
        # A dual-band AP supporting 802.11a/b (2.4GHz) and 802.11b/g (5GHz).
        mock_ap2 = self.MockAp(
            bands_and_modes=[{'band': self.ap_config.BAND_2GHZ,
                              'modes': [self.ap_config.MODE_A,
                                        self.ap_config.MODE_B]},
                             {'band': self.ap_config.BAND_5GHZ,
                              'modes': [self.ap_config.MODE_B,
                                        self.ap_config.MODE_G]}])
        test_aps = [mock_ap1, mock_ap2]
        # Find APs that supports 802.11a only.
        actual = self.factory._get_aps_with_modes(
            [self.ap_config.MODE_A], test_aps)
        self.assertEquals([mock_ap1, mock_ap2], actual)
        # Find APs that supports 802.11a/b.
        actual = self.factory._get_aps_with_modes(
            [self.ap_config.MODE_A, self.ap_config.MODE_B], test_aps)
        self.assertEquals([mock_ap1, mock_ap2], actual)
        # Find APs that supports 802.11g only.
        actual = self.factory._get_aps_with_modes(
            [self.ap_config.MODE_G], test_aps)
        self.assertEquals([mock_ap2], actual)


    def testGetApsWithSecurities_WithEmptySecurities(self):
        """Test with empty securities and empty ap_list."""
        self.assertEquals(None, self.factory._get_aps_with_securities([], []))


    def testGetApsWithSecurities_WithInvalidSecuritiesOnly(self):
        """Test with invalid securities and empty ap_list."""
        actual = self.factory._get_aps_with_securities([-1], [])
        self.assertEquals(None, actual)

    def testGetApsWithSecurities_WithValidSecuritiesAndEmptyApList(self):
        """Test with valid securities and empty ap_list."""
        actual = self.factory._get_aps_with_securities(
            [self.ap_config.SECURITY_TYPE_DISABLED], [])
        self.assertEquals([], actual)


    def testGetApsWithSecurities_WithValidSecuritiesAndApListReturnsOne(self):
        """Test with valid securities and ap_list."""
        mock_ap1 = self.MockAp(
            supported_securities=[self.ap_config.SECURITY_TYPE_DISABLED,
                                  self.ap_config.SECURITY_TYPE_WEP])
        mock_ap2 = self.MockAp(
            supported_securities=[self.ap_config.SECURITY_TYPE_WEP,
                                  self.ap_config.SECURITY_TYPE_WPAPSK])
        test_aps = [mock_ap1, mock_ap2]
        # Find only APs that supports open system.
        actual = self.factory._get_aps_with_securities(
            [self.ap_config.SECURITY_TYPE_DISABLED], test_aps)
        self.assertEquals([mock_ap1], actual)
        # Find only APs that supports WEP.
        actual = self.factory._get_aps_with_securities(
            [self.ap_config.SECURITY_TYPE_WEP], test_aps)
        self.assertEquals([mock_ap1, mock_ap2], actual)
        # Find APs that supports both WEP and PSK.
        actual = self.factory._get_aps_with_securities(
            [self.ap_config.SECURITY_TYPE_WEP,
             self.ap_config.SECURITY_TYPE_WPAPSK], test_aps)
        self.assertEquals([mock_ap2], actual)
        # Find APs that supports both open system and PSK.
        actual = self.factory._get_aps_with_securities(
            [self.ap_config.SECURITY_TYPE_DISABLED,
             self.ap_config.SECURITY_TYPE_WPAPSK], test_aps)
        self.assertEquals([], actual)
        # Find only APs that supports WPA2PSK.
        actual = self.factory._get_aps_with_securities(
            [self.ap_config.SECURITY_TYPE_WPA2PSK], test_aps)
        self.assertEquals([], actual)


    def testGetApConfigurators_WithEmptySpec(self):
        """Test with empty spec."""
        test_ap_list = ['fake_ap']
        self.factory.ap_list = test_ap_list
        self.assertEquals(test_ap_list, self.factory.get_ap_configurators())
        self.assertEquals(test_ap_list, self.factory.get_ap_configurators({}))


    def testGetApConfigurators_WithInvalidKeys(self):
        """Test with a spec of invalid keys only."""
        test_ap_list = ['fake_ap']
        self.factory.ap_list = test_ap_list
        self.assertEquals(
            test_ap_list, self.factory.get_ap_configurators(dict(foo=1)))


    def testGetApConfigurators_WithOneKey(self):
        """Test with a spec of one valid key."""
        mock_ap1 = self.MockAp(
            bands_and_channels=[{'band': self.ap_config.BAND_2GHZ,
                                 'channels': [5]}])
        mock_ap2 = self.MockAp(
            bands_and_modes=[{'band': self.ap_config.BAND_2GHZ,
                              'modes': [self.ap_config.MODE_A,
                                        self.ap_config.MODE_B]},
                             {'band': self.ap_config.BAND_5GHZ,
                              'modes': [self.ap_config.MODE_B,
                                        self.ap_config.MODE_G]}])
        mock_ap3 = self.MockAp(
            supported_securities=[self.ap_config.SECURITY_TYPE_DISABLED,
                                  self.ap_config.SECURITY_TYPE_WEP])
        test_ap_list = [mock_ap1, mock_ap2, mock_ap3]
        self.factory.ap_list = test_ap_list
        ap_by_bands = self.factory.get_ap_configurators(
            dict(bands=[self.ap_config.BAND_2GHZ]))
        self.assertEquals([mock_ap1], ap_by_bands)
        ap_by_modes = self.factory.get_ap_configurators(
            dict(modes=[self.ap_config.MODE_G]))
        self.assertEquals([mock_ap2], ap_by_modes)
        ap_by_securities = self.factory.get_ap_configurators(
            dict(securities=[self.ap_config.SECURITY_TYPE_DISABLED]))
        self.assertEquals([mock_ap3], ap_by_securities)


    def testGetApConfigurators_WithMultipleKeys(self):
        """Test with a spec of multiple valid keys."""
        # AP1 supports 2.4GHz band, 802.11a/b, open system and WEP.
        mock_ap1 = self.MockAp(
            bands_and_channels=[{'band': self.ap_config.BAND_2GHZ,
                                 'channels': [5]}],
            bands_and_modes=[{'band': self.ap_config.BAND_2GHZ,
                              'modes': [self.ap_config.MODE_A,
                                        self.ap_config.MODE_B]}],
            supported_securities=[self.ap_config.SECURITY_TYPE_DISABLED,
                                  self.ap_config.SECURITY_TYPE_WEP],
            )
        # AP2 supports 5GHz band, 802.11b/g, open system and WPA PSK.
        mock_ap2 = self.MockAp(
            bands_and_channels=[{'band': self.ap_config.BAND_5GHZ,
                                 'channels': [48]}],
            bands_and_modes=[{'band': self.ap_config.BAND_5GHZ,
                              'modes': [0x0010, self.ap_config.MODE_G]}],
            supported_securities=[self.ap_config.SECURITY_TYPE_DISABLED,
                                  self.ap_config.SECURITY_TYPE_WPAPSK],
            )
        # AP3 supports dual-band, 802.11a/b/g, WEP and WPA PSK.
        mock_ap3 = self.MockAp(
            bands_and_channels=[{'band': self.ap_config.BAND_2GHZ,
                                 'channels': [5]},
                                {'band': self.ap_config.BAND_5GHZ,
                                 'channels': [48]}],
            bands_and_modes=[{'band': self.ap_config.BAND_2GHZ,
                              'modes': [self.ap_config.MODE_B,
                                        self.ap_config.MODE_N]},
                             {'band': self.ap_config.BAND_5GHZ,
                              'modes': [self.ap_config.MODE_B,
                                        self.ap_config.MODE_G]}],
            supported_securities=[self.ap_config.SECURITY_TYPE_WEP,
                                  self.ap_config.SECURITY_TYPE_WPAPSK],
            )
        test_ap_list = [mock_ap1, mock_ap2, mock_ap3]
        self.factory.ap_list = test_ap_list

        # Find APs that support 2.4GHz band and 802.11b
        actual = self.factory.get_ap_configurators(
            dict(bands=[self.ap_config.BAND_2GHZ],
                 modes=[self.ap_config.MODE_B]))
        self.assertEquals([mock_ap1, mock_ap3], actual)
        # Find APs that support 5GHz band and WPA PSK
        actual = self.factory.get_ap_configurators(
            dict(bands=[self.ap_config.BAND_5GHZ],
                 securities=[self.ap_config.SECURITY_TYPE_WPAPSK]))
        self.assertEquals([mock_ap2, mock_ap3], actual)
        # Find APs that support 802.11b band and open system
        actual = self.factory.get_ap_configurators(
            dict(modes=[self.ap_config.MODE_B],
                 securities=[self.ap_config.SECURITY_TYPE_DISABLED]))
        self.assertEquals([mock_ap1, mock_ap2], actual)
        # Find APs that support 2.4GHz band and 802.11a
        actual = self.factory.get_ap_configurators(
            dict(bands=[self.ap_config.BAND_2GHZ],
                 modes=[self.ap_config.MODE_A]))
        self.assertEquals([mock_ap1], actual)
        # Find APs that support 2.4GHz band and 802.11 b/g
        actual = self.factory.get_ap_configurators(
            dict(bands=[self.ap_config.BAND_2GHZ],
                 modes=[self.ap_config.MODE_B, self.ap_config.MODE_G]))
        self.assertEquals([mock_ap3], actual)
        # Find APs that support 5GHz band and open system
        actual = self.factory.get_ap_configurators(
            dict(bands=[self.ap_config.BAND_5GHZ],
                 securities=[self.ap_config.SECURITY_TYPE_DISABLED]))
        self.assertEquals([mock_ap2], actual)
        # Find APs that support 5GHz band, 802.11 auto and WPA PSK
        actual = self.factory.get_ap_configurators(
            dict(bands=[self.ap_config.BAND_5GHZ],
                 modes=[self.ap_config.MODE_N],
                 securities=[self.ap_config.SECURITY_TYPE_WPAPSK]))
        self.assertEquals([mock_ap3], actual)
        # Find APs that support 2.4GHz band and WPA2 PSK
        actual = self.factory.get_ap_configurators(
            dict(bands=[self.ap_config.BAND_2GHZ],
                 securities=[self.ap_config.SECURITY_TYPE_WPA2PSK]))
        self.assertEquals([], actual)


    """New tests that cover the new ap_spec use case."""
    def _build_ap_test_inventory(self):
        # AP1 supports 2.4GHz band, all modes, and all securities.
        self.mock_ap1 = self.MockAp(
            bands_and_channels=[{'band': ap_spec.BAND_2GHZ,
                                 'channels': ap_spec.VALID_2GHZ_CHANNELS}],
            bands_and_modes=[{'band': ap_spec.BAND_2GHZ,
                              'modes': ap_spec.VALID_2GHZ_MODES}],
            supported_securities=ap_spec.VALID_SECURITIES,
            host_name='mock_ap1',
            )
        # AP2 supports 2.4 and 5 GHz, all modes, open system, and visibility.
        self.mock_ap2 = self.MockAp(
            bands_and_channels=[{'band': ap_spec.BAND_2GHZ,
                                 'channels': ap_spec.VALID_2GHZ_CHANNELS},
                                {'band': ap_spec.BAND_5GHZ,
                                 'channels': ap_spec.VALID_5GHZ_CHANNELS}],
            bands_and_modes=[{'band': ap_spec.BAND_2GHZ,
                              'modes': ap_spec.VALID_2GHZ_MODES},
                             {'band': ap_spec.BAND_5GHZ,
                              'modes': ap_spec.VALID_5GHZ_MODES}],
            supported_securities=[ap_spec.SECURITY_TYPE_DISABLED],
            visibility_supported=True,
            host_name='mock_ap2',
            )
        self.factory.ap_list = [self.mock_ap1, self.mock_ap2]


    def testGetApConfigurators_WithBandAPSpec(self):
        """Test with a band only specified AP Spec"""
        self._build_ap_test_inventory()

        spec = ap_spec.APSpec(band=ap_spec.BAND_2GHZ)
        actual = self.factory.get_ap_configurators_by_spec(ap_spec=spec)
        self.assertEquals([self.mock_ap1, self.mock_ap2].sort(), actual.sort())

        spec = ap_spec.APSpec(band=ap_spec.BAND_5GHZ)
        actual = self.factory.get_ap_configurators_by_spec(ap_spec=spec)
        self.assertEquals([self.mock_ap2], actual)


    def testGetAPConfigurators_WithModeAPSpec(self):
        """Test with a mode only specified AP Spec"""
        self._build_ap_test_inventory()

        spec = ap_spec.APSpec(mode=ap_spec.DEFAULT_2GHZ_MODE)
        actual = self.factory.get_ap_configurators_by_spec(ap_spec=spec)
        self.assertEquals([self.mock_ap1, self.mock_ap2].sort(), actual.sort())

        spec = ap_spec.APSpec(mode=ap_spec.DEFAULT_5GHZ_MODE)
        actual = self.factory.get_ap_configurators_by_spec(ap_spec=spec)
        self.assertEquals([self.mock_ap2], actual)


    def testGetAPConfigurators_WithSecurityAPSpec(self):
        """Test with a security only specified AP Spec"""
        self._build_ap_test_inventory()
        spec = ap_spec.APSpec(security=ap_spec.SECURITY_TYPE_WPAPSK)
        actual = self.factory.get_ap_configurators_by_spec(ap_spec=spec)
        self.assertEquals([self.mock_ap1], actual)


    def testGetAPConfigurators_WithVisibilityAPSpec(self):
        """Test with a visibility specified AP Spec."""
        self._build_ap_test_inventory()

        spec = ap_spec.APSpec(visible=True)
        actual = self.factory.get_ap_configurators_by_spec(ap_spec=spec)
        self.assertEquals([self.mock_ap1, self.mock_ap2].sort(), actual.sort())

        spec = ap_spec.APSpec(band=ap_spec.BAND_5GHZ, visible=False)
        actual = self.factory.get_ap_configurators_by_spec(ap_spec=spec)
        self.assertEquals([self.mock_ap2], actual)


    def testGetAPConfigurators_ByHostName(self):
        """Test obtaining a list of APs by hostname."""
        self._build_ap_test_inventory()

        actual = self.factory.get_aps_configurators_by_hostnames(['mock_ap1'])
        self.assertEquals([self.mock_ap1], actual)

        actual = self.factory.get_aps_configurators_by_hostnames(['mock_ap1',
                                                                  'mock_ap2'])
        self.assertEquals([self.mock_ap1, self.mock_ap2].sort(), actual.sort())


    def testGetAndPreConfigureAPConfigurators(self):
        """Test preconfiguring APs."""
        self._build_ap_test_inventory()

        # Pick something that is not the default channel.
        channel = ap_spec.VALID_5GHZ_CHANNELS[-1]
        spec = ap_spec.APSpec(channel=channel)
        actual = self.factory.get_ap_configurators_by_spec(ap_spec=spec,
                                                           pre_configure=True)
        self.assertEquals([self.mock_ap2], actual)
        self.assertEquals(actual[0].get_channel(), channel)
