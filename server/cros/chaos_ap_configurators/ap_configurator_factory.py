# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys
from autotest_lib.server.cros.chaos_config import ChaosAPList

import asus_ap_configurator
import belkin_ap_configurator
import buffalo_ap_configurator
import dlink_ap_configurator
import dlink_dir655_ap_configurator
import dlinkwbr1310_ap_configurator
import linksys_ap_configurator
import linksys_ap_15_configurator
import linksyse_dual_band_configurator
import linksyse_single_band_configurator
import linksyse2000_ap_configurator
import linksyse2100_ap_configurator
import linksyse2500_ap_configurator
import netgear3700_ap_configurator
import netgear4300_ap_configurator
import netgearR6200_ap_configurator
import netgear2000_ap_configurator
import netgear_WNDR_dual_band_configurator
import netgear_single_band_configurator
import trendnet_ap_configurator


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
        'DLinkDIR655APConfigurator':
            dlink_dir655_ap_configurator.DLinkDIR655APConfigurator,
        'BuffaloAPConfigurator':
            buffalo_ap_configurator.BuffaloAPConfigurator,
        'AsusAPConfigurator':
            asus_ap_configurator.AsusAPConfigurator,
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
        'NetgearSingleBandAPConfigurator':
            netgear_single_band_configurator.NetgearSingleBandAPConfigurator,
        'DLinkwbr1310APConfigurator':
            dlinkwbr1310_ap_configurator.DLinkwbr1310APConfigurator,
        'Linksyse2100APConfigurator':
            linksyse2100_ap_configurator.Linksyse2100APConfigurator,
        'LinksyseSingleBandAPConfigurator':
            linksyse_single_band_configurator.LinksyseSingleBandAPConfigurator,
        'Linksyse2500APConfigurator':
            linksyse2500_ap_configurator.Linksyse2500APConfigurator
    }

    def __init__(self):
        chaos_config = ChaosAPList(static_config=False)

        self.ap_list = []
        for ap in chaos_config:
            configurator = self.configurator_map[ap.get_class()]
            self.ap_list.append(configurator(ap))

    def get_ap_configurators(self):
        return self.ap_list

    def get_ap_configurator_by_short_name(self, name):
        for ap in self.ap_list:
            if ap.get_router_short_name() == name:
                return ap
        return None

    def turn_off_all_routers(self):
        for ap in self.ap_list:
            ap.power_down_router()
