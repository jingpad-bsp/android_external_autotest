# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ConfigParser
import logging
import os
import time

from autotest_lib.site_utils.rpm_control_system import rpm_client

TIMEOUT = 100

class APPowerException(Exception):
    """ Exception raised when AP fails to power on. """
    pass

class APSectionError(Exception):
    """ Exception raised when AP instance does not exist in the config. """
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
    CHANNEL_TABLE = {2412: 1, 2417: 2, 2422: 3,
                     2427: 4, 2432: 5, 2437: 6,
                     2442: 7, 2447: 8, 2452: 9,
                     2457: 10, 2462: 11, 2467: 12,
                     2472: 13, 2484: 14, 5180: 36,
                     5200: 40, 5220: 44, 5240: 48,
                     5745: 149, 5765: 153, 5785: 157,
                     5805: 161, 5825: 165}

    # This only works because the frequency table is
    # one to one for Channels/Frequencies.
    FREQUENCY_TABLE = dict((v,k) for k,v in CHANNEL_TABLE.iteritems())

    # Needed for ap_configurator interoperability
    BAND_2GHZ = '2.4GHz'
    BAND_5GHZ = '5GHz'


    def __init__(self, bss, config):
        """
        Intialize object

        @param bss: string containing bssid
        @param config: ConfigParser read from file

        """
        if not config.has_section(bss):
            raise APSectionError('BSS (%s) not defined.' % bss)
        self.bss = bss
        self.ap_config = config


    def get_ssid(self):
        """@return string ssid for AP from config file"""
        return self.ap_config.get(self.bss, self.CONF_SSID)


    def get_brand(self):
        """@return string brand for AP from config file"""
        return self.ap_config.get(self.bss, self.CONF_BRAND)


    def get_model(self):
        """@return string model for AP from config file"""
        return self.ap_config.get(self.bss, self.CONF_MODEL)


    def get_wan_mac(self):
        """@return string mac for WAN port of AP from config file"""
        return self.ap_config.get(self.bss, self.CONF_WAN_MAC)


    def get_wan_host(self):
        """@return string host for AP from config file"""
        return self.ap_config.get(self.bss, self.CONF_WAN_HOST)


    def get_bss(self):
        """@return string bss for AP from config file"""
        return self.ap_config.get(self.bss, self.CONF_BSS)


    def get_bss5(self):
        """@return string bss5 for AP from config file"""
        return self.ap_config.get(self.bss, self.CONF_BSS5)


    def get_bandwidth(self):
        """@return string bandwidth for AP from config file"""
        return self.ap_config.get(self.bss, self.CONF_BANDWIDTH)


    def get_security(self):
        """@return string security for AP from config file"""
        return self.ap_config.get(self.bss, self.CONF_SECURITY)


    def get_psk(self):
        """@return string psk for AP from config file"""
        return self.ap_config.get(self.bss, self.CONF_PSK)


    def get_frequency(self):
        """@return int frequency for AP from config file"""
        return int(self.ap_config.get(self.bss, self.CONF_FREQUENCY))

    def get_channel(self):
        """@return int channel for AP from config file"""
        return self.CHANNEL_TABLE[self.get_frequency()]


    def get_band(self):
        """@return string band for AP from config file"""
        if self.get_frequency() < 4915:
            return self.BAND_2GHZ
        else:
            return self.BAND_5GHZ


    def get_class(self):
        """@return string class for AP from config file"""
        return self.ap_config.get(self.bss, self.CONF_CLASS)


    def get_admin(self):
        """@return string admin for AP from config file"""
        return self.ap_config.get(self.bss, self.CONF_ADMIN)


    def power_off(self):
        """call rpm_client to power off AP"""
        rpm_client.set_power(self.get_wan_host(), 'OFF')


    def power_on(self):
        """call rpm_client to power on AP"""
        rpm_client.set_power(self.get_wan_host(), 'ON')

        # Hard coded timer for now to wait for the AP to come alive
        # before trying to use it.  We need scanning code
        # to scan until the AP becomes available (crosbug.com/36710).
        time.sleep(TIMEOUT)


    def __str__(self):
        """@return string description of AP"""
        ap_info = {
            'brand': self.get_brand(),
            'model': self.get_model(),
            'ssid' : self.get_ssid(),
            'bss'  : self.get_bss(),
            'hostname': self.get_wan_host(),
        }
        return ('AP Info:\n'
                '  Name:      %(brand)s %(model)s\n'
                '  SSID:      %(ssid)s\n'
                '  BSS:       %(bss)s\n'
                '  Hostname:  %(hostname)s\n' % ap_info)


class ChaosAPList(object):
    """ Object containing information about all AP's in the chaos lab. """

    DYNAMIC_AP_CONFIG_FILE = 'chaos_dynamic_ap_list.conf'


    def __init__(self):
        """initialize object by reading config file"""
        self.ap_config = ConfigParser.RawConfigParser()
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            self.DYNAMIC_AP_CONFIG_FILE)

        logging.debug('Reading config from "%s"', path)
        self.ap_config.read(path)


    def get_ap_by_bss(self, bss):
        """
        finds AP from bssid string in config file

        @param bss: a string containing bssid of desired AP
        @return ChaosAP object created from bssid lookup in config

        """
        return ChaosAP(bss, self.ap_config)


    def next(self):
        """
        read next AP from config file

        @return ChaosAP object created from bssid lookup in config

        """
        bss = self._iterptr.next()
        return self.get_ap_by_bss(bss)


    def __iter__(self):
        """
        iterated through bssid sections in config file

        @return iterator for next section

        """
        self._iterptr = self.ap_config.sections().__iter__()
        return self
