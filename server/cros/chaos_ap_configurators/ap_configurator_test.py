# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit test for ap_configurator."""

import os
import sys
import unittest

# Define autotest_lib MAGIC!
sys.path.append(os.path.join(
                os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
from utils import common

import ap_batch_locker


class ConfiguratorTest(unittest.TestCase):
    """This test needs to be run against the UI interface of a real AP.

    The purpose of this test is to act as a basic acceptance test when
    developing a new AP configurator class.  Use this to make sure all core
    functionality is implemented.

    This test does not verify that everything works for ALL APs. It only
    tests against the AP specified below in AP_SPEC.

    Launch this unit test from outside chroot:
      $ cd ~/chromeos/src/third_party/autotest/files
      $ python utils/unittest_suite.py \
        server.cros.chaos_ap_configurators.ap_configurator_test --debug

    To run a single test, from outside chroot, e.g.
      $ cd ~/chromeos/src/third_party/autotest/files/\
           server/cros/chaos_ap_configurators
      $ python -m unittest ap_configurator_test.ConfiguratorTest.test_ssid
    """

    # Specify the Chaos AP to run the tests against.
    AP_SPEC = dict(hostnames=['chromeos3-row1-rack2-host11'])


    @classmethod
    def setUpClass(self):
        self.batch_locker = ap_batch_locker.ApBatchLocker(self.AP_SPEC)
        ap_batch = self.batch_locker.get_ap_batch(batch_size=1)
        if not ap_batch:
            raise RuntimeError('Unable to lock AP %r' % self.AP_SPEC)
        self.ap = ap_batch[0]
        print('Powering up the AP (this may take a minute...)')
        self.ap._power_up_router()


    @classmethod
    def tearDownClass(self):
        if self.batch_locker:
            self.batch_locker.unlock_aps()
        self.ap._power_down_router()


    def setUp(self):
        # All tests have to have a band pre-set.
        bands = self.ap.get_supported_bands()
        self.ap.set_band(bands[0]['band'])
        self.ap.apply_settings()


    def disabled_security_on_all_bands(self):
        """Disables security on all available bands."""
        for band in self.ap.get_supported_bands():
            self.ap.set_band(band['band'])
            self.ap.set_security_disabled()
            self.ap.apply_settings()


    def return_non_n_mode_pair(self):
        """Returns a mode and band that do not contain wireless mode N.

        Wireless N does not support several wifi security modes.  In order
        to test they can be configured that makes it easy to select an
        available compatible mode.
        """
        # Make this return something that does not contain N
        return_dict = {}
        for mode in self.ap.get_supported_modes():
            return_dict['band'] = mode['band']
            for mode_type in mode['modes']:
                if mode_type & self.ap.mode_n != self.ap.mode_n:
                    return_dict['mode'] = mode_type
        return return_dict


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
        supported_bands = self.ap.get_supported_bands()
        for band in supported_bands:
            self.ap.set_band(band['band'])
            # Set to the second available channel
            self.ap.set_channel(band['channels'][1])
            self.ap.apply_settings()


    def test_visibility(self):
        """Test adjusting the visibility."""
        self.ap.set_visibility(False)
        self.ap.apply_settings()
        self.ap.set_visibility(True)
        self.ap.apply_settings()


    def test_ssid(self):
        """Test setting the SSID."""
        bands_info = self.ap.get_supported_bands()
        self.assertTrue(bands_info, msg='Invalid band sent.')
        for bands in bands_info:
            band = bands['band']
            if band == self.ap.band_2ghz:
                self.ap.set_band(band)
                self.ap.set_ssid('ssid2')
                self.ap.apply_settings()
            if band == self.ap.band_5ghz:
                self.ap.set_band(band)
                self.ap.set_ssid('ssid5')
                self.ap.apply_settings()


    def test_band(self):
        """Test switching the band."""
        self.ap.set_band(self.ap.band_2ghz)
        self.ap.apply_settings()
        self.ap.set_band(self.ap.band_5ghz)
        self.ap.apply_settings()


    def test_switching_bands_and_change_settings(self):
        """Test switching between bands and change settings for each band."""
        bands_info = self.ap.get_supported_bands()
        self.assertTrue(bands_info, msg='Invalid band sent.')
        bands_set = [d['band'] for d in bands_info]
        for band in bands_set:
            self.ap.set_band(band)
            self.ap.set_ssid('pqrstu_' + band)
            self.ap.set_visibility(True)
            if self.ap.is_security_mode_supported(self.ap.security_type_wep):
                self.ap.set_security_wep('test2',
                                         self.ap.wep_authentication_open)
            self.ap.apply_settings()


    def test_invalid_security(self):
        """Test an exception is thrown for an invalid configuration."""
        self.disabled_security_on_all_bands()
        for mode in self.ap.get_supported_modes():
            if not self.ap.mode_n in mode['modes']:
                return
        if not self.ap.is_security_mode_supported(self.ap.security_type_wep):
            return
        self.ap.set_mode(self.ap.mode_n)
        self.ap.set_security_wep('77777', self.ap.wep_authentication_open)
        try:
            self.ap.apply_settings()
        except RuntimeError, e:
            self.ap.driver.close()
            message = str(e)
            if message.find('no handler was specified') != -1:
                self.fail('Subclass did not handle an alert.')
            return
        self.fail('An exception should have been thrown but was not.')


    def test_security_wep(self):
        """Test configuring WEP security."""
        if not self.ap.is_security_mode_supported(self.ap.security_type_wep):
            return
        for mode in self.ap.get_supported_modes():
            self.ap.set_band(mode['band'])
            for mode_type in mode['modes']:
                if mode_type & self.ap.mode_n != self.ap.mode_n:
                    self.ap.set_mode(mode_type)
                    self.ap.set_security_wep('45678',
                                             self.ap.wep_authentication_open)
                    self.ap.apply_settings()
                    self.ap.set_security_wep('90123',
                                             self.ap.wep_authentication_shared)
                    self.ap.apply_settings()


    def test_priority_sets(self):
        """Test that commands are run in the right priority."""
        self.ap.set_radio(enabled=False)
        self.ap.set_visibility(True)
        self.ap.set_ssid('prioritytest')
        self.ap.apply_settings()


    def test_security_and_general_settings(self):
        """Test updating settings that are general and security related."""
        self.disabled_security_on_all_bands()
        good_pair = self.return_non_n_mode_pair()
        self.ap.set_radio(enabled=False)
        self.ap.set_band(good_pair['band'])
        self.ap.set_mode(good_pair['mode'])
        self.ap.set_visibility(True)
        if self.ap.is_security_mode_supported(self.ap.security_type_wep):
            self.ap.set_security_wep('88888', self.ap.wep_authentication_open)
        self.ap.set_ssid('secgentest')
        self.ap.apply_settings()


    def test_modes(self):
        """Tests switching modes."""
        # Some security settings won't work with some modes
        self.ap.set_security_disabled()
        self.ap.apply_settings()
        modes_info = self.ap.get_supported_modes()
        self.assertTrue(modes_info,
                        msg='Returned an invalid mode list.  Is this method'
                        ' implemented?')
        for band_modes in modes_info:
            self.ap.set_band(band_modes['band'])
            for mode in band_modes['modes']:
                self.ap.set_mode(mode)
                self.ap.apply_settings()


    def test_modes_with_band(self):
        """Tests switching modes that support adjusting the band."""
        # Different bands and security options conflict.  Disable security for
        # this test.
        self.disabled_security_on_all_bands()
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
        self.disabled_security_on_all_bands()
        self.ap.set_radio(enabled=True)
        if self.ap.is_security_mode_supported(self.ap.security_type_wep):
            self.ap.set_security_wep('77777', self.ap.wep_authentication_open)
        if self.ap.is_security_mode_supported(self.ap.security_type_disabled):
            self.ap.set_security_disabled()
        if self.ap.is_security_mode_supported(self.ap.security_type_wpapsk):
            self.ap.set_security_wpapsk('qwertyuiolkjhgfsdfg')
        self.ap.apply_settings()


    def test_cycle_security(self):
        """Test switching between different security settings."""
        self.disabled_security_on_all_bands()
        good_pair = self.return_non_n_mode_pair()
        self.ap.set_radio(enabled=True)
        self.ap.set_band(good_pair['band'])
        self.ap.set_mode(good_pair['mode'])
        if self.ap.is_security_mode_supported(self.ap.security_type_wep):
            self.ap.set_security_wep('77777', self.ap.wep_authentication_open)
        self.ap.apply_settings()
        if self.ap.is_security_mode_supported(self.ap.security_type_disabled):
            self.ap.set_security_disabled()
        self.ap.apply_settings()
        if self.ap.is_security_mode_supported(self.ap.security_type_wpapsk):
            self.ap.set_security_wpapsk('qwertyuiolkjhgfsdfg')
        self.ap.apply_settings()


    def test_actions_when_radio_disabled(self):
        """Test making changes when the radio is disabled."""
        self.disabled_security_on_all_bands()
        good_pair = self.return_non_n_mode_pair()
        self.ap.set_radio(enabled=False)
        self.ap.set_band(good_pair['band'])
        self.ap.set_mode(good_pair['mode'])
        self.ap.apply_settings()
        if self.ap.is_security_mode_supported(self.ap.security_type_wep):
            self.ap.set_security_wep('77777', self.ap.wep_authentication_open)
        self.ap.set_radio(enabled=False)
        self.ap.apply_settings()


    def test_power_cycle_router(self):
        """Test powering the ap down and back up again."""
        self.ap.power_cycle_router_up()


if __name__ == '__main__':
    unittest.main()
