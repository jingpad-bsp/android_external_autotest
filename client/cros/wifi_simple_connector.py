# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import cros_ui

class WifiSimpleConnector(object):
    """Simple class that uses pyauto calls to connected to a wifi network."""


    def __init__(self, pyauto_object):
        self.pyauto = pyauto_object


    def connect_to_wifi_network(self, ssid=None, ssid_visible=True,
                                wifi_security='SECURITY_NONE',
                                wifi_password=''):
        if not ssid:
            raise error.TestError(
                'Invalid configuration, a ssid must be specificed.')
        if wifi_security not in ('SECURITY_NONE', 'SECURITY_WEP',
                                 'SECURITY_WPA', 'SECURITY_RSN',
                                 'SECURITY_8021X'):
            raise error.TestError('Invalid security type.')

        device_path = None
        if ssid_visible:
            device_path = self.pyauto.GetServicePath(ssid)
            if not device_path:
                raise error.TestError('Unable to locate the visible ssid %s.' %
                                      ssid)
            err = self.pyauto.ConnectToWifiNetwork(device_path,
                                                   password=wifi_password)
            if err:
                msg = ('Failed to connect to wifi network %s. Reason: %s.'
                       % (ssid, err))
                raise error.TestError(msg)
        else:
            err = self.pyauto.ConnectToHiddenWifiNetwork(ssid, wifi_security,
                                                         password=wifi_password)
        if err:
            msg = ('Failed to connect to wifi network %s. Reason: %s.' %
                   (ssid, err))
            raise error.TestError(msg)
        self.pyauto.NavigateToURL('http://www.google.com')
        if self.pyauto.GetActiveTabTitle() != 'Google':
            msg = ('Unable to connect to google.com, network is mis-configured '
                   'or was unable to connect to wifi network. Error: %s' % e)
            raise error.TestError(msg)

        logging.debug('Connection successful.')
