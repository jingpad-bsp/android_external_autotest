# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

import dlink_ap_configurator
import linksys_ap_configurator
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
        config_dict = None
        try:
            config_dict = eval(contents)
        except Exception, e:
            raise RuntimeError('%s is an invalid data file.' %
                               config_dict_file_path)
        self.ap_list = [
            linksys_ap_configurator.LinksysAPConfigurator(
                config_dict['LinksysAPConfigurator']),
            dlink_ap_configurator.DLinkAPConfigurator(
                config_dict['DLinkAPConfigurator']),
            trendnet_ap_configurator.TrendnetAPConfigurator(
                config_dict['TrendnetAPConfigurator'])]

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
