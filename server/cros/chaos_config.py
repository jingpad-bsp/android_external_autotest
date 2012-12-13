# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ConfigParser
import logging
import os
import time
import xmlrpclib

from autotest_lib.site_utils.rpm_control_system import rpm_client

class APPowerException(Exception):
    pass


class ChaosAP(object):
    """ An instance of an ap defined in the chaos config file.

    This object is a wrapper that can be used to retrieve information
    about an AP in the chaos lab, and control its power.
    """


    # Keys used in the config file.
    CONF_SSID = 'ssid'
    CONF_BRAND = 'brand'
    CONF_MODEL = 'model'
    CONF_WAN_MAC = 'wan mac'
    CONF_WAN_HOST = 'wan_hostname'
    CONF_BSS = 'bss'
    CONF_BSS5 = 'bss5'
    CONF_BANDWIDTH = 'bandwidth'
    CONF_SECURITY = 'security'
    CONF_PSK = 'psk'
    CONF_FREQUENCY = 'frequency'
    CONF_BAND = 'band'
    CONF_CHANNEL = 'channel'
    CONF_CLASS = 'class_name'
    CONF_ADMIN = 'admin_url'

    # Frequency to channel conversion table
    CHANNEL_TABLE = {'2412': '1', '2417': '2', '2422': '3',
                     '2427': '4', '2432': '5', '2437': '6',
                     '2442': '7', '2447': '8', '2452': '9',
                     '2457': '10', '2462': '11', '2467': '12',
                     '2472': '13', '2484': '14', '5180': '36',
                     '5200': '40', '5220': '44', '5240': '48',
                     '5745': '149', '5765': '153', '5785': '157',
                     '5805': '161', '5825': '165'}
    # Needed for ap_configurator interoperability
    BAND_2GHZ = '2.4GHz'
    BAND_5GHZ = '5GHz'


    def __init__(self, bss, config):
        self.bss = bss
        self.ap_config = config


    def get_ssid(self):
        return self.ap_config.get(self.bss, self.CONF_SSID)


    def get_brand(self):
        return self.ap_config.get(self.bss, self.CONF_BRAND)


    def get_model(self):
        return self.ap_config.get(self.bss, self.CONF_MODEL)


    def get_wan_mac(self):
        return self.ap_config.get(self.bss, self.CONF_WAN_MAC)


    def get_wan_host(self):
        return self.ap_config.get(self.bss, self.CONF_WAN_HOST)


    def get_bss(self):
        return self.ap_config.get(self.bss, self.CONF_BSS)


    def get_bss5(self):
        return self.ap_config.get(self.bss, self.CONF_BSS5)


    def get_bandwidth(self):
        return self.ap_config.get(self.bss, self.CONF_BANDWIDTH)


    def get_security(self):
        return self.ap_config.get(self.bss, self.CONF_SECURITY)


    def get_psk(self):
        return self.ap_config.get(self.bss, self.CONF_PSK)


    def get_frequency(self):
        return self.ap_config.get(self.bss, self.CONF_FREQUENCY)


    def get_channel(self):
        return self.CHANNEL_TABLE[self.get_frequency()]


    def get_band(self):
        if int(frequency) < 4915:
            return self.BAND_2GHZ
        else:
            return self.BAND_5GHZ


    def get_class(self):
        return self.ap_config.get(self.bss, self.CONF_CLASS)


    def get_admin(self):
        return self.ap_config.get(self.bss, self.CONF_ADMIN)


    def power_off(self):
        rpm_client.set_power(self.get_wan_host(), 'OFF')


    def power_on(self):
        rpm_client.set_power(self.get_wan_host(), 'ON')

        # Hard coded timer for now to wait for the AP to come alive
        # before trying to use it.  We need scanning code
        # to scan until the AP becomes available (crosbug.com/36710).
        time.sleep(60)


class ChaosAPList(object):
    """ Object containing information about all AP's in the chaos lab. """

    DYNAMIC_AP_CONFIG_FILE = 'chaos_dynamic_ap_list.conf'
    STATIC_AP_CONFIG_FILE = 'chaos_static_ap_list.conf'


    def __init__(self, static_config=True):
        self.ap_config = ConfigParser.RawConfigParser()
        if static_config:
            config_file = self.STATIC_AP_CONFIG_FILE
        else:
            config_file = self.DYNAMIC_AP_CONFIG_FILE
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            config_file)

        logging.debug('Reading config from "%s"', path)
        self.ap_config.read(path)


    def get_ap_by_bss(self, bss):
        return ChaosAP(bss, self.ap_config)


    def next(self):
        bss = self._iterptr.next()
        return self.get_ap_by_bss(bss)


    def __iter__(self):
        self._iterptr = self.ap_config.sections().__iter__()
        return self
