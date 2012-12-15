# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys
sys.path.append('../')
from chaos_config import ChaosAPList

import asus_ap_configurator
import belkin_ap_configurator
import buffalo_ap_configurator
import dlink_ap_configurator
import dlink_dir655_ap_configurator
import dlinkwbr1310_ap_configurator
import linksys_ap_configurator
import linksyse900_ap_configurator
import linksyse2000_ap_configurator
import linksyse2100_ap_configurator
import linksyse2700_ap_configurator
import linksyse3500_ap_configurator
import linksyse4200_ap_configurator
import netgear3700_ap_configurator
import netgear4500_ap_configurator
import trendnet_ap_configurator
import netgear614_ap_configurator


class APConfiguratorFactory(object):
    """Class that instantiates all available APConfigurators."""

    configurator_map = {
        'LinksysAPConfigurator':
            linksys_ap_configurator.LinksysAPConfigurator,
        'DLinkAPConfigurator':
            dlink_ap_configurator.DLinkAPConfigurator,
        'TrendnetAPConfigurator' :
            trendnet_ap_configurator.TrendnetAPConfigurator,
        'DLinkDIR655APConfigurator':
            dlink_dir655_ap_configurator.DLinkDIR655APConfigurator,
        'BuffaloAPConfigurator':
            buffalo_ap_configurator.BuffaloAPConfigurator,
        'AsusAPConfigurator':
            asus_ap_configurator.AsusAPConfigurator,
        'Netgear3700APConfigurator':
            netgear3700_ap_configurator.Netgear3700APConfigurator,
        'Linksyse4200APConfigurator':
            linksyse4200_ap_configurator.Linksyse4200APConfigurator,
        'Linksyse2000APConfigurator':
            linksyse2000_ap_configurator.Linksyse2000APConfigurator,
        'Netgear4500APConfigurator':
            netgear4500_ap_configurator.NetgearAPConfigurator,
        'BelkinAPConfigurator':
            belkin_ap_configurator.BelkinAPConfigurator,
        'Netgear614APConfigurator':
            netgear614_ap_configurator.NetgearAPConfigurator,
        'DLinkwbr1310APConfigurator':
            dlinkwbr1310_ap_configurator.DLinkwbr1310APConfigurator,
        'Linksyse3500APConfigurator':
            linksyse3500_ap_configurator.Linksyse3500APConfigurator,
        'Linksyse2100APConfigurator':
            linksyse2100_ap_configurator.Linksyse2100APConfigurator,
        'Linksyse2700APConfigurator':
            linksyse2700_ap_configurator.Linksyse2700APConfigurator,
        'Linksyse900APConfigurator':
            linksyse900_ap_configurator.Linksyse900APConfigurator,
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
