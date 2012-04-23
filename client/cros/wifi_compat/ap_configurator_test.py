# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

import ap_configurator_factory
import download_chromium_prebuilt


class ConfiguratorTest(unittest.TestCase):
    """This test needs to be run against the UI interface.

    The purpose of this test is to act as a basic acceptance test when
    developing a new AP configurator class.  Use this to make sure all core
    functionality is implemented.

    This test does not verify that everything works.

    This class provides a fast way to test without having to run_remote_test
    because chances are you don't need a ChromeOS device.  You will need to run
    this like:
    $ PYTHONPATH=../../deps/pyauto_dep/test_src/third_party/webdriver/pylib/
      python ap_configurator_test.py
    """

    def setUp(self):
        if download_chromium_prebuilt.download_chromium_prebuilt_binaries():
            self.fail('The binaries were just downloaded.  Please run: '
                      '(outside-chroot) <path to chroot tmp directory>/'
                      '%s./chromedriver',
                      download_chromium_prebuilt.DOWNLOAD_PATH)
        config_path = os.path.join(os.path.dirname(__file__),
                                   '..', '..', 'config', 'wifi_compat_config')
        factory = ap_configurator_factory.APConfiguratorFactory(config_path)
        # Set self.ap to the one you want to test against.
        self.ap = factory.get_ap_configurator_by_short_name('TEW-639GR')

    def test_make_no_changes(self):
        """Test saving with no changes doesn't throw an error."""
        # Set to a known state.
        self.ap.set_radio(enabled=True)
        self.ap.apply_settings()
        # Set the same setting again.
        self.ap.set_radio(enabled=True)
        self.ap.apply_settings()

    def test_radio(self):
        """Test we can adjust the radio setting."""
        self.ap.set_radio(enabled=True)
        self.ap.apply_settings()
        self.ap.set_radio(enabled=False)
        self.ap.apply_settings()

    def test_channel(self):
        """Test adjusting the channel."""
        self.ap.set_radio(enabled=True)
        self.ap.set_channel(4)
        self.ap.apply_settings()

    def test_visibility(self):
        """Test adjusting the visibility."""
        self.ap.set_visibility(False)
        self.ap.apply_settings()
        self.ap.set_visibility(True)
        self.ap.apply_settings()

    def test_ssid(self):
        """Test setting the SSID."""
        self.ap.set_ssid('AP-automated-ssid')
        self.ap.apply_settings()

    def test_security_wep(self):
        """Test configuring WEP security."""
        if self.ap.is_security_mode_supported(self.ap.security_wep):
            self.ap.set_security_wep('45678', self.ap.wep_authentication_open)
            self.ap.apply_settings()
            self.ap.set_security_wep('90123', self.ap.wep_authentication_shared)
            self.ap.apply_settings()

    def test_priority_sets(self):
        """Test that commands are run in the right priority."""
        self.ap.set_radio(enabled=False)
        self.ap.set_visibility(True)
        self.ap.set_ssid('priority_test')
        self.ap.apply_settings()

    def test_security_and_general_settings(self):
        """Test updating settings that are general and security related."""
        self.ap.set_radio(enabled=False)
        self.ap.set_visibility(True)
        if self.ap.is_security_mode_supported(self.ap.security_wep):
            self.ap.set_security_wep('88888', self.ap.wep_authentication_open)
        self.ap.set_ssid('sec&gen_test')
        self.ap.apply_settings()

    def test_modes(self):
        """Tests switching modes."""
        modes_info = self.ap.get_supported_modes()
        self.assertTrue(modes_info,
                         msg='Returned an invalid mode list.  Is this method'
                         ' implemented?')
        for band_modes in modes_info:
            for mode in band_modes['modes']:
                self.ap.set_mode(mode)
                self.ap.apply_settings()

    def test_modes_with_band(self):
        """Tests switching modes that support adjusting the band."""
        # Check if we support self.kModeN across multiple bands
        modes_info = self.ap.get_supported_modes()
        n_bands = []
        for band_modes in modes_info:
            if self.ap.mode_n in band_modes['modes']:
                n_bands.append(band_modes['band'])
        if len(n_bands) > 1:
            for n_band in n_bands:
                self.ap.set_mode(self.ap.mode_n, band=n_band)
                self.ap.apply_settings()

    def test_fast_cycle_security(self):
        """Mini stress for changing security settings rapidly."""
        self.ap.set_radio(enabled=True)
        if self.ap.is_security_mode_supported(self.ap.security_wep):
            self.ap.set_security_wep('77777', self.ap.wep_authentication_open)
        if self.ap.is_security_mode_supported(self.ap.security_disabled):
            self.ap.set_security_disabled()
        if self.ap.is_security_mode_supported(self.ap.security_wpapsk):
            self.ap.set_security_wpapsk('qwertyuiolkjhgfsdfg')
        self.ap.apply_settings()

    def test_cycle_security(self):
        """Test switching between different security settings."""
        self.ap.set_radio(enabled=True)
        if self.ap.is_security_mode_supported(self.ap.security_wep):
            self.ap.set_security_wep('77777', self.ap.wep_authentication_open)
        self.ap.apply_settings()
        if self.ap.is_security_mode_supported(self.ap.security_disabled):
            self.ap.set_security_disabled()
        self.ap.apply_settings()
        if self.ap.is_security_mode_supported(self.ap.security_wpapsk):
            self.ap.set_security_wpapsk('qwertyuiolkjhgfsdfg')
        self.ap.apply_settings()

    def test_actions_when_radio_disabled(self):
        """Test making changes when the radio is disabled."""
        self.ap.set_radio(enabled=False)
        self.ap.apply_settings()
        if self.ap.is_security_mode_supported(self.ap.security_wep):
            self.ap.set_security_wep('77777', self.ap.wep_authentication_open)
        self.ap.set_radio(enabled=False)
        self.ap.apply_settings()


if __name__ == '__main__':
    unittest.main()
