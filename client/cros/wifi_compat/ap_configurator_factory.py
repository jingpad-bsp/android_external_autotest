# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

import asus_ap_configurator
import buffalo_ap_configurator
import dlink_ap_configurator
import dlink_dir655_ap_configurator
import linksys_ap_configurator
import linksyse2000_ap_configurator
import linksysE4200_ap_configurator
import Netgear3700_ap_configurator
import trendnet_ap_configurator

class APConfiguratorFactory(object):
    """Class that instantiates all available APConfigurators."""

    def __init__(self, config_dict_file_path):
        if not os.path.exists(config_dict_file_path):
            raise IOError('The configuration file at path %s is missing' %
                          str(config_dict_file_path))

        f = open(config_dict_file_path)
        contents = f.read()
        f.close()
        config_list = None
        try:
            config_list = eval(contents)
        except Exception, e:
            raise RuntimeError('%s is an invalid data file.' %
                               config_dict_file_path)
        self.ap_list = []
        self._build_all_instances_of_configurator(config_list,
            'LinksysAPConfigurator',
            linksys_ap_configurator.LinksysAPConfigurator)
        self._build_all_instances_of_configurator(config_list,
            'DLinkAPConfigurator',
            dlink_ap_configurator.DLinkAPConfigurator)
        self._build_all_instances_of_configurator(config_list,
            'TrendnetAPConfigurator',
            trendnet_ap_configurator.TrendnetAPConfigurator)
        self._build_all_instances_of_configurator(config_list,
            'DLinkDIR655APConfigurator',
            dlink_dir655_ap_configurator.DLinkDIR655APConfigurator)
        self._build_all_instances_of_configurator(config_list,
            'BuffaloAPConfigurator',
            buffalo_ap_configurator.BuffaloAPConfigurator)
        self._build_all_instances_of_configurator(config_list,
            'AsusAPConfigurator',
            asus_ap_configurator.AsusAPConfigurator)
        self._build_all_instances_of_configurator(config_list,
            'Netgear3700APConfigurator',
            Netgear3700_ap_configurator.Netgear3700APConfigurator)
        self._build_all_instances_of_configurator(config_list,
            'LinksysE4200APConfigurator',
            linksysE4200_ap_configurator.LinksysAPConfigurator)
        self._build_all_instances_of_configurator(config_list,
            'linksyse2000APConfigurator',
            linksyse2000_ap_configurator.linksyse2000APConfigurator)

    def _build_all_instances_of_configurator(self, config_list, name,
                                             configurator):
        for current in config_list:
            if current['class_name'] == name:
                self.ap_list.append(configurator(current))

    def get_ap_configurators(self):
        return self.ap_list

    def get_ap_configurator_by_short_name(self, name):
        for ap in self.ap_list:
            if ap.get_router_short_name() == name:
                return ap
        return None

    def turn_off_all_routers(self):
        for ap in self.ap_list:
            ap.set_radio(enabled=False)
            ap.apply_settings()
