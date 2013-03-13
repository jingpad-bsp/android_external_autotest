# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""File containing class to build all available ap_configurators."""

from autotest_lib.server.cros.chaos_ap_configurators import ap_cartridge
from autotest_lib.server.cros.chaos_config import ChaosAPList

import asus_ap_configurator
import asus_ac66r_ap_configurator
import asus_qis_ap_configurator
import belkin_ap_configurator
import belkinF9K_ap_configurator
import buffalo_ap_configurator
import dlink_ap_configurator
import dlink_dir655_ap_configurator
import dlinkwbr1310_ap_configurator
import linksys_ap_configurator
import linksys_ap_15_configurator
import linksyse_dual_band_configurator
import linksyse_single_band_configurator
import linksyse1000_ap_configurator
import linksyse2000_ap_configurator
import linksyse2100_ap_configurator
import linksyse2500_ap_configurator
import linksyswrt160_ap_configurator
import medialink_ap_configurator
import netgear3700_ap_configurator
import netgear4300_ap_configurator
import netgearR6200_ap_configurator
import netgear2000_ap_configurator
import netgear_WNDR_dual_band_configurator
import netgear_single_band_configurator
import trendnet_ap_configurator
import trendnet691gr_ap_configurator
import westerndigitaln600_ap_configurator


class APConfiguratorFactory(object):
    """Class that instantiates all available APConfigurators."""

    configurator_map = {
        'LinksysAPConfigurator':
            linksys_ap_configurator.LinksysAPConfigurator,
        'LinksysAP15Configurator':
            linksys_ap_15_configurator.LinksysAP15Configurator,
        'DLinkAPConfigurator':
            dlink_ap_configurator.DLinkAPConfigurator,
        'TrendnetAPConfigurator':
            trendnet_ap_configurator.TrendnetAPConfigurator,
        'Trendnet691grAPConfigurator':
            trendnet691gr_ap_configurator.Trendnet691grAPConfigurator,
        'DLinkDIR655APConfigurator':
            dlink_dir655_ap_configurator.DLinkDIR655APConfigurator,
        'BuffaloAPConfigurator':
            buffalo_ap_configurator.BuffaloAPConfigurator,
        'AsusAPConfigurator':
            asus_ap_configurator.AsusAPConfigurator,
        'AsusQISAPConfigurator':
            asus_qis_ap_configurator.AsusQISAPConfigurator,
        'Asus66RAPConfigurator':
            asus_ac66r_ap_configurator.Asus66RAPConfigurator,
        'Netgear3700APConfigurator':
            netgear3700_ap_configurator.Netgear3700APConfigurator,
        'NetgearR6200APConfigurator':
            netgearR6200_ap_configurator.NetgearR6200APConfigurator,
        'Netgear2000APConfigurator':
            netgear2000_ap_configurator.Netgear2000APConfigurator,
        'Netgear4300APConfigurator':
            netgear4300_ap_configurator.Netgear4300APConfigurator,
        'LinksyseDualBandAPConfigurator':
            linksyse_dual_band_configurator.LinksyseDualBandAPConfigurator,
        'Linksyse2000APConfigurator':
            linksyse2000_ap_configurator.Linksyse2000APConfigurator,
        'NetgearDualBandAPConfigurator':
            netgear_WNDR_dual_band_configurator.NetgearDualBandAPConfigurator,
        'BelkinAPConfigurator':
            belkin_ap_configurator.BelkinAPConfigurator,
        'BelkinF9KAPConfigurator':
            belkinF9K_ap_configurator.BelkinF9KAPConfigurator,
        'MediaLinkAPConfigurator':
            medialink_ap_configurator.MediaLinkAPConfigurator,
        'NetgearSingleBandAPConfigurator':
            netgear_single_band_configurator.NetgearSingleBandAPConfigurator,
        'DLinkwbr1310APConfigurator':
            dlinkwbr1310_ap_configurator.DLinkwbr1310APConfigurator,
        'Linksyse2100APConfigurator':
            linksyse2100_ap_configurator.Linksyse2100APConfigurator,
        'LinksyseSingleBandAPConfigurator':
            linksyse_single_band_configurator.LinksyseSingleBandAPConfigurator,
        'Linksyse2500APConfigurator':
            linksyse2500_ap_configurator.Linksyse2500APConfigurator,
        'WesternDigitalN600APConfigurator':
            westerndigitaln600_ap_configurator.WesternDigitalN600APConfigurator,
        'Linksyse1000APConfigurator':
            linksyse1000_ap_configurator.Linksyse1000APConfigurator,
        'LinksysWRT160APConfigurator':
            linksyswrt160_ap_configurator.LinksysWRT160APConfigurator,
    }

    def __init__(self):
        chaos_config = ChaosAPList(static_config=False)

        self.ap_list = []
        for ap in chaos_config:
            configurator = self.configurator_map[ap.get_class()]
            self.ap_list.append(configurator(ap_config=ap))


    def get_ap_configurators(self):
        """Returns all available configurators."""
        return self.ap_list


    def get_ap_configurator_by_short_name(self, name):
        """
        Returns a configurator by short name.

        @param name: short name of the configurator
        """
        for ap in self.ap_list:
            if ap.get_router_short_name() == name:
                return ap
        return None


    def get_aps_with_security_mode(self, security_mode, ap_list=None):
        """
        Returns all configurators that support a given security mode.

        @param security_mode: desired security mode
        @param ap_list: the aps to query for the desired security mode.

        @returns a list of APs.
        """
        if not ap_list:
          ap_list = self.ap_list
        aps = []
        for ap in ap_list:
            if ap.is_security_mode_supported(security_mode):
                aps.append(ap)
        return aps


    def get_supported_bands_and_channels(self, ap_list=None):
        """
        Returns all of the supported bands and channels.

        Format of the return dictionary:
        {self.band_2GHz : [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
         self.band_5ghz : [26, 40, 44, 48, 149, 153, 165]}

        @param ap_list: list of aps to build the supported bands and channels.

        @returns a dictionary of bands and channels.
        """
        if not ap_list:
            ap_list = self.ap_list
        bands_and_channels = {}
        for ap in ap_list:
            bands = ap.get_supported_bands()
            for band in bands:
                if band['band'] not in bands_and_channels:
                    bands_and_channels[band['band']] = set(band['channels'])
                else:
                    bands_and_channels[band['band']].union(band['channels'])
        return bands_and_channels


    def turn_off_all_routers(self):
        """Powers down all of the routers."""
        ap_power_cartridge = ap_cartridge.APCartridge()
        for ap in self.ap_list:
            ap.power_down_router()
            ap_power_cartridge.push_configurator(ap)
        ap_power_cartridge.run_configurators()
