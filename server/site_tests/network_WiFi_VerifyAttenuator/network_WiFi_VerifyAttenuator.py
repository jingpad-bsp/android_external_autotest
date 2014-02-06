# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.server.cros.network import attenuator_controller
from autotest_lib.server.cros.network import hostap_config
from autotest_lib.server.cros.network import rvr_test_base

STARTING_ATTENUATION = 60
ATTENUATION_STEP = 4
FINAL_ATTENUATION = 80
ATTENUATORS_PER_PHY = 2


class network_WiFi_VerifyAttenuator(rvr_test_base.RvRTestBase):
    """Test that all connected attenuators are functioning correctly."""
    version = 1


    def _get_phy_num_for_instance(self, instance):
        """Get the phy number corresponding to a hostapd instance.

        @param instance: int hostapd instance to test against.
        @return int phy number corresponding to that AP (e.g.
                for phy0 return 0).

        """
        phy = self.context.router.get_hostapd_phy(instance)
        if not phy.startswith('phy'):
            raise error.TestError('Unexpected phy name %s' % phy)

        return int(phy[3:])


    def _verify_attenuator(self, ap_num, frequency_mhz, attenuator_num):
        """Verify that each phy has two attenuators controlling its signal.

        @param ap_num: int hostapd instance to test against.
        @param frequency_mhz: int frequency of the AP.
        @param attenuator_num: int attenuator num controlling one antenna on
                the AP.
        @return bool: True iff the test passes.

        """
        # Remove knowledge of previous networks from shill.
        self.context.client.shill.init_test_network_state()
        # Isolate the client entirely.
        self.context.attenuator.set_variable_attenuation(
                attenuator_controller.MAX_VARIABLE_ATTENUATION)
        # But allow one antenna on this phy.
        self.context.attenuator.set_variable_attenuation(
                0, attenuator_num=attenuator_num)
        # Leave a little time for client state to settle down.
        time.sleep(5)
        client_conf = xmlrpc_datatypes.AssociationParameters(
                ssid=self.context.router.get_ssid(instance=ap_num))
        logging.info('Connecting to %s', client_conf.ssid)
        assoc_result = xmlrpc_datatypes.deserialize(
                self.context.client.shill.connect_wifi(client_conf))
        if not assoc_result.success:
            logging.error('Failed to connect to AP %d on attenuator %d',
                          ap_num, attenuator_num)
            return False
        logging.info('Connected successfully')
        for atten in range(STARTING_ATTENUATION,
                           FINAL_ATTENUATION + 1,
                           ATTENUATION_STEP):
            self.context.attenuator.set_total_attenuation(
                    atten, frequency_mhz, attenuator_num=attenuator_num)
            time.sleep(2)
            logging.info('Attenuator %d signal at attenuation=%d is %d dBm.',
                         attenuator_num, atten,
                         self.context.client.wifi_signal_level)
        return True


    def _verify_phy_attenuator_correspondence(self, instance):
        """Verify that we cannot connect to a phy when it is attenuated.

        Check that putting maximum attenuation on the attenuators expected
        to gate a particular phy produces the expected result.  We should
        be unable to connect to the corresponding SSID.

        @param instance: int hostapd instance to verify corresponds to
                a particular 2 attenuators.

        """
        # Turn up all attenuation.
        self.context.attenuator.set_variable_attenuation(
                attenuator_controller.MAX_VARIABLE_ATTENUATION)
        # Turn down attenuation for phys other than the instance we're
        # interested in.
        for other_instance in [x for x in range(self.num_phys)
                                 if x != instance]:
            other_phy_num = self._get_phy_num_for_instance(other_instance)
            for attenuator_offset in range(ATTENUATORS_PER_PHY):
                attenuator_num = (other_phy_num * ATTENUATORS_PER_PHY +
                                  attenuator_offset)
                self.context.attenuator.set_variable_attenuation(
                        0, attenuator_num=attenuator_num)
        # We should be unable to connect.
        client_conf = xmlrpc_datatypes.AssociationParameters(
                ssid=self.context.router.get_ssid(instance=instance),
                expect_failure=True)
        self.context.assert_connect_wifi(client_conf)


    def run_once(self):
        """For each PHY on a router, for 2 and 5 Ghz bands on a PHY:

        1) Set up an AP on the PHY.
        2) Walk the attenuators from low to high attenuations.
        3) Measure AP signal as attenuation increases.
        4) Tester should manually inspect that signal levels decrease linearly
           and are consistent from attenuator to attenuator.

        """
        self.num_phys = len(self.context.router.iw_runner.list_phys())
        any_failed = False
        # Pick channels other than the calibrated ones.
        for channel in (8, 132):
            ap_config = hostap_config.HostapConfig(
                    channel=channel,
                    mode=hostap_config.HostapConfig.MODE_11N_PURE)
            self.context.router.deconfig_aps()
            for _ in range(self.num_phys):
                self.context.configure(ap_config, multi_interface=True)
            for instance in range(self.num_phys):
                if self.num_phys > 1:
                    self._verify_phy_attenuator_correspondence(instance)
                phy_num = self._get_phy_num_for_instance(instance)
                for attenuator_offset in range(ATTENUATORS_PER_PHY):
                    attenuator_num = (phy_num * ATTENUATORS_PER_PHY +
                                      attenuator_offset)
                    if not self._verify_attenuator(
                            instance, ap_config.frequency, attenuator_num):
                        any_failed = True
        if any_failed:
            raise error.TestFail('One or more attenuators are broken!')
