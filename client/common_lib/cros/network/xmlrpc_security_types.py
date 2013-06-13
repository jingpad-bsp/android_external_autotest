# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys

from autotest_lib.client.common_lib.cros import xmlrpc_datatypes

TYPE_KEY = 'security_class_type_key'

def deserialize(serialized):
    """Deserialize a SecurityConfig.

    Because Python XMLRPC doesn't understand anything more than basic
    types, we're forced to reinvent type marshalling.  This is one way
    to do it.

    @param serialized dict representing a serialized SecurityConfig.
    @return a SecurityConfig object built from |serialized|.

    """
    if TYPE_KEY not in serialized:
        return None

    return getattr(sys.modules[__name__],
                   serialized[TYPE_KEY])(serialized=serialized)


class SecurityConfig(xmlrpc_datatypes.XmlRpcStruct):
    """Abstracts the security configuration for a WiFi network.

    This bundle of credentials can be passed to both HostapConfig and
    AssociationParameters so that both shill and hostapd can set up and connect
    to an encrypted WiFi network.  By default, we'll assume we're connecting
    to an open network.

    """
    SERVICE_PROPERTY_PASSPHRASE = 'Passphrase'

    def __init__(self, serialized=None, security=None):
        super(SecurityConfig, self).__init__()
        setattr(self, TYPE_KEY, self.__class__.__name__)
        if serialized is None:
            serialized = {}
        # Default to no security.
        self.security = serialized.get('security', security or 'none')


    def get_hostapd_config(self):
        """@return dict fragment of hostapd configuration for security."""
        return {}


    def get_shill_service_properties(self):
        """@return dict of shill service properties."""
        return {}


    def __repr__(self):
        return '%s(security=%r)' % (self.__class__.__name__, self.security)


class WEPConfig(SecurityConfig):
    """Abstracts security configuration for a WiFi network using static WEP."""

    def __init__(self, serialized=None, wep_keys=None, wep_default_key=None):
        super(WEPConfig, self).__init__(serialized=serialized, security='wep')
        if serialized is None:
            serialized = {}
        self.wep_keys = serialized.get('wep_keys', wep_keys or [])
        self.wep_default_key = serialized.get('wep_default_key',
                                              wep_default_key or 0)
        if self.wep_keys and len(self.wep_keys) > 4:
            raise error.TestFail('More than 4 WEP keys specified (%d).' %
                                 len(self.wep_keys))


    def get_hostapd_config(self):
        """@return dict fragment of hostapd configuration for security."""
        ret = {}
        for idx,key in enumerate(self.wep_keys):
            ret['wep_key%d' % idx] = key
        ret['wep_default_key'] = self.wep_default_key
        return ret


    def get_shill_service_properties(self):
        """@return dict of shill service properties."""
        return {self.SERVICE_PROPERTY_PASSPHRASE: '%d:%s' % (
                        self.wep_default_key,
                        self.wep_keys[self.wep_default_key])}


    def __repr__(self):
        return '%s(wep_keys=%r, wep_default_key=%r)' % (self.__class__.__name__,
                                                        self.wep_keys,
                                                        self.wep_default_key)
