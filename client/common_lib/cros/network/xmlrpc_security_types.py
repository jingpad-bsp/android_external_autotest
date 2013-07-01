# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import random
import stat
import string
import sys
import tempfile

from autotest_lib.client.common_lib.cros import xmlrpc_types


def deserialize(serialized):
    """Deserialize a SecurityConfig.

    @param serialized dict representing a serialized SecurityConfig.
    @return a SecurityConfig object built from |serialized|.

    """
    return xmlrpc_types.deserialize(serialized, module=sys.modules[__name__])


class SecurityConfig(xmlrpc_types.XmlRpcStruct):
    """Abstracts the security configuration for a WiFi network.

    This bundle of credentials can be passed to both HostapConfig and
    AssociationParameters so that both shill and hostapd can set up and connect
    to an encrypted WiFi network.  By default, we'll assume we're connecting
    to an open network.

    """
    SERVICE_PROPERTY_PASSPHRASE = 'Passphrase'

    def __init__(self, security='none'):
        super(SecurityConfig, self).__init__()
        self.security = security


    def get_hostapd_config(self):
        """@return dict fragment of hostapd configuration for security."""
        return {}


    def get_shill_service_properties(self):
        """@return dict of shill service properties."""
        return {}


    def install_files(self, router_host, client_host):
        """Install the necessary credentials on the hosts involved.

        @param router_host host object representing the router.
        @param client_host host object representing the DUT.

        """
        # Unless we're installing certificates, we usually don't need this.
        pass


    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           ', '.join(['%s=%r' % item
                                      for item in vars(self).iteritems()]))


class WEPConfig(SecurityConfig):
    """Abstracts security configuration for a WiFi network using static WEP."""
    # Open system authentication means that we don't do a 4 way AUTH handshake,
    # and simply start using the WEP keys after association finishes.
    AUTH_ALGORITHM_OPEN = 1
    # This refers to a mode where the AP sends a plaintext challenge and the
    # client sends back the challenge encrypted with the WEP key as part of a 4
    # part auth handshake.
    AUTH_ALGORITHM_SHARED = 2
    AUTH_ALGORITHM_DEFAULT = AUTH_ALGORITHM_OPEN

    def __init__(self, wep_keys, wep_default_key=0,
                 auth_algorithm=AUTH_ALGORITHM_DEFAULT):
        """Construct a WEPConfig object.

        @param wep_keys list of string WEP keys.
        @param wep_default_key int 0 based index into |wep_keys| for the default
                key.
        @param auth_algorithm int bitfield of AUTH_ALGORITHM_* defined above.

        """
        super(WEPConfig, self).__init__(security='wep')
        self.wep_keys = wep_keys
        self.wep_default_key = wep_default_key
        self.auth_algorithm = auth_algorithm
        if self.auth_algorithm & ~(self.AUTH_ALGORITHM_OPEN |
                                   self.AUTH_ALGORITHM_SHARED):
            raise error.TestFail('Invalid authentication mode specified (%d).' %
                                 self.auth_algorithm)

        if self.wep_keys and len(self.wep_keys) > 4:
            raise error.TestFail('More than 4 WEP keys specified (%d).' %
                                 len(self.wep_keys))


    def get_hostapd_config(self):
        """@return dict fragment of hostapd configuration for security."""
        ret = {}
        for idx,key in enumerate(self.wep_keys):
            ret['wep_key%d' % idx] = key
        ret['wep_default_key'] = self.wep_default_key
        ret['auth_algs'] = self.auth_algorithm
        return ret


    def get_shill_service_properties(self):
        """@return dict of shill service properties."""
        return {self.SERVICE_PROPERTY_PASSPHRASE: '%d:%s' % (
                        self.wep_default_key,
                        self.wep_keys[self.wep_default_key])}


class WPAConfig(SecurityConfig):
    """Abstracts security configuration for a WPA encrypted WiFi network."""

    # We have the option of turning on WPA, WPA2, or both via a bitfield.
    MODE_PURE_WPA = 1
    MODE_PURE_WPA2 = 2
    MODE_MIXED_WPA = MODE_PURE_WPA | MODE_PURE_WPA2
    MODE_DEFAULT = MODE_MIXED_WPA

    # WPA2 mandates the use of AES in CCMP mode.
    # WPA allows the use of 'ordinary' AES, but mandates support for TKIP.
    # The protocol however seems to indicate that you just list a bunch of
    # different ciphers that you support and we'll start speaking one.
    CIPHER_CCMP = 'CCMP'
    CIPHER_TKIP = 'TKIP'

    def __init__(self, psk='', wpa_mode=MODE_DEFAULT, wpa_ciphers=[],
                 wpa2_ciphers=[], wpa_ptk_rekey_period=None):
        """Construct a WPAConfig.

        @param psk string a passphrase (64 hex characters or an ASCII phrase up
                to 63 characters long).
        @param wpa_mode int one of MODE_* above.
        @param wpa_ciphers list of ciphers to advertise in the WPA IE.
        @param wpa2_ciphers list of ciphers to advertise in the WPA2 IE.
                hostapd will fall back on WPA ciphers for WPA2 if this is
                left unpopulated.
        @param wpa_ptk_rekey_period int number of seconds between PTK rekeys.

        """
        super(WPAConfig, self).__init__(security='psk')
        self.psk = psk
        self.wpa_mode = wpa_mode
        self.wpa_ciphers = wpa_ciphers
        self.wpa2_ciphers = wpa2_ciphers
        self.wpa_ptk_rekey_period = wpa_ptk_rekey_period


    def get_hostapd_config(self):
        """@return dict fragment of hostapd configuration for security."""
        if not self.wpa_mode:
            raise error.TestFail('Cannot configure WPA unless we know which '
                                 'mode to use.')

        if self.MODE_PURE_WPA & self.wpa_mode and not self.wpa_ciphers:
            raise error.TestFail('Cannot configure WPA unless we know which '
                                 'ciphers to use.')

        if not self.wpa_ciphers and not self.wpa2_ciphers:
            raise error.TestFail('Cannot configure WPA2 unless we have some '
                                 'ciphers.')

        ret = {'wpa': self.wpa_mode,
               'wpa_key_mgmt': 'WPA-PSK',
               'wpa_passphrase': self.psk}
        if self.wpa_ciphers:
            ret['wpa_pairwise'] = ' '.join(self.wpa_ciphers)
        if self.wpa2_ciphers:
            ret['rsn_pairwise'] = ' '.join(self.wpa2_ciphers)
        if self.wpa_ptk_rekey_period:
            ret['wpa_ptk_rekey'] = self.wpa_ptk_rekey_period
        return ret


    def get_shill_service_properties(self):
        """@return dict of shill service properties."""
        return {self.SERVICE_PROPERTY_PASSPHRASE: self.psk}


class EAPConfig(SecurityConfig):
    """Abstract superclass that implements certificate/key installation."""

    SERVICE_PROPERTY_CA_CERT = 'EAP.CACert'
    SERVICE_PROPERTY_CLIENT_CERT = 'EAP.ClientCert'
    SERVICE_PROPERTY_EAP_IDENTITY = 'EAP.Identity'
    SERVICE_PROPERTY_EAP_KEY_MGMT = 'EAP.KeyMgmt'
    SERVICE_PROPERTY_PRIVATE_KEY = 'EAP.PrivateKey'
    SERVICE_PROPERTY_USE_SYSTEM_CAS = 'EAP.UseSystemCAs'

    def __init__(self, security='802_1x', file_suffix=None, use_system_cas=None,
                 server_ca_cert=None, server_cert=None, server_key=None,
                 client_ca_cert=None, client_cert=None, client_key=None):
        """Construct an EAPConfig.

        @param file_suffix string unique file suffix on DUT.
        @param use_system_cas False iff we should ignore server certificates.
        @param server_ca_cert string PEM encoded CA certificate for the server.
        @param server_cert string PEM encoded identity certificate for server.
        @param server_key string PEM encoded private key for server.
        @param client_ca_cert string PEM encoded CA certificate for client.
        @param client_cert string PEM encoded identity certificate for client.
        @param client_key string PEM encoded private key for client.

        """
        super(EAPConfig, self).__init__(security=security)
        self.use_system_cas = use_system_cas
        self.server_ca_cert = server_ca_cert
        self.server_cert = server_cert
        self.server_key = server_key
        self.client_ca_cert = client_ca_cert
        self.client_cert = client_cert
        self.client_key = client_key
        if file_suffix is None:
            suffix_letters = string.ascii_lowercase + string.digits
            file_suffix = ''.join(random.choice(suffix_letters)
                                  for x in range(10))
            logging.debug('Choosing unique file_suffix %s.', file_suffix)
        self.server_ca_cert_file = '/tmp/hostapd_ca_cert_file.' + file_suffix
        self.server_cert_file = '/tmp/hostapd_cert_file.' + file_suffix
        self.server_key_file = '/tmp/hostapd_key_file.' + file_suffix
        self.server_eap_user_file = '/tmp/hostapd_eap_user_file.' + file_suffix
        self.client_ca_cert_file = '/tmp/pkg_ca_cert.' + file_suffix
        self.client_cert_file = '/tmp/pkg_cert.' + file_suffix
        self.client_key_file = '/tmp/pkg_key.' + file_suffix
        # While these paths won't make it across the network, the suffix will.
        self.file_suffix = file_suffix


    def install_files(self, router_host, client_host):
        """Install the necessary credentials on the hosts involved.

        @param router_host host object representing the router.
        @param client_host host object representing the DUT.

        """
        files = [(router_host, self.server_ca_cert, self.server_ca_cert_file),
                 (router_host, self.server_cert, self.server_cert_file),
                 (router_host, self.server_key, self.server_key_file),
                 (router_host, '* TLS', self.server_eap_user_file),
                 (client_host, self.client_ca_cert, self.client_ca_cert_file),
                 (client_host, self.client_cert, self.client_cert_file),
                 (client_host, self.client_key, self.client_key_file)]
        for host, content, path in files:
            # If we omit a parameter, just omit copying a file over.
            if content is None:
                continue
            # Write the contents to local disk first so we can use the easy
            # built in mechanism to do this.
            with tempfile.NamedTemporaryFile() as f:
                f.write(content)
                f.flush()
                os.chmod(f.name, stat.S_IRUSR | stat.S_IWUSR |
                                 stat.S_IRGRP | stat.S_IWGRP |
                                 stat.S_IROTH | stat.S_IWOTH)
                host.send_file(f.name, path, delete_dest=True)


    def get_shill_service_properties(self):
        """@return dict of shill service properties."""
        ret = {}
        ret = {# We hardcoded this user into those certificates.
               self.SERVICE_PROPERTY_EAP_IDENTITY: 'chromeos'}
        if self.client_ca_cert:
            ret[self.SERVICE_PROPERTY_CA_CERT] = self.client_ca_cert_file
        if self.client_cert:
            ret[self.SERVICE_PROPERTY_CLIENT_CERT] = self.client_cert_file
        if self.client_key:
            ret[self.SERVICE_PROPERTY_PRIVATE_KEY] = self.client_key_file
        if self.use_system_cas is not None:
            ret[self.SERVICE_PROPERTY_USE_SYSTEM_CAS] = self.use_system_cas
        return ret


    def get_hostapd_config(self):
        """@return dict fragment of hostapd configuration for security."""
        return {'ieee8021x': 1, # Enable 802.1x support.
                'eap_server' : 1, # Do EAP inside hostapd to avoid RADIUS.
                'ca_cert': self.server_ca_cert_file,
                'server_cert': self.server_cert_file,
                'private_key': self.server_key_file,
                'eap_user_file': self.server_eap_user_file}


class DynamicWEPConfig(EAPConfig):
    """Configuration settings bundle for dynamic WEP.

    This is a WEP encrypted connection where the keys are negotiated after the
    client authenticates via 802.1x.

    """

    DEFAULT_REKEY_PERIOD = 20


    def __init__(self, use_short_keys=False,
                 wep_rekey_period=DEFAULT_REKEY_PERIOD,
                 server_ca_cert=None, server_cert=None, server_key=None,
                 client_ca_cert=None, client_cert=None, client_key=None,
                 file_suffix=None):
        """Construct a DynamicWEPConfig.

        @param use_short_keys bool force hostapd to use 40 bit WEP keys.
        @param wep_rekey_period int number of second between rekeys.
        @param server_ca_cert string PEM encoded CA certificate for the server.
        @param server_cert string PEM encoded identity certificate for server.
        @param server_key string PEM encoded private key for server.
        @param client_ca_cert string PEM encoded CA certificate for client.
        @param client_cert string PEM encoded identity certificate for client.
        @param client_key string PEM encoded private key for client.
        @param file_suffix string unique file suffix on DUT.

        """
        super(DynamicWEPConfig, self).__init__(
                security='wep', file_suffix=file_suffix,
                server_ca_cert=server_ca_cert, server_cert=server_cert,
                server_key=server_key, client_ca_cert=client_ca_cert,
                client_cert=client_cert, client_key=client_key)
        self.use_short_keys = use_short_keys
        self.wep_rekey_period = wep_rekey_period


    def get_hostapd_config(self):
        """@return dict fragment of hostapd configuration for security."""
        ret = super(DynamicWEPConfig, self).get_hostapd_config()
        key_len = 13 # 128 bit WEP, 104 secret bits.
        if self.use_short_keys:
            key_len = 5 # 64 bit WEP, 40 bits of secret.
        ret.update({'wep_key_len_broadcast': key_len,
                    'wep_key_len_unicast': key_len,
                    'wep_rekey_period': self.wep_rekey_period})
        return ret


    def get_shill_service_properties(self):
        """@return dict of shill service properties."""
        ret = super(DynamicWEPConfig, self).get_shill_service_properties()
        ret.update({self.SERVICE_PROPERTY_EAP_KEY_MGMT: 'IEEE8021X'})
        return ret


class WPAEAPConfig(EAPConfig):
    """Security type to set up a WPA tunnel via EAP-TLS negotiation."""

    def __init__(self, file_suffix=None, use_system_cas=None,
                 server_ca_cert=None, server_cert=None, server_key=None,
                 client_ca_cert=None, client_cert=None, client_key=None):
        """Construct a DynamicWEPConfig.

        @param file_suffix string unique file suffix on DUT.
        @param use_system_cas False iff we should ignore server certificates.
        @param server_ca_cert string PEM encoded CA certificate for the server.
        @param server_cert string PEM encoded identity certificate for server.
        @param server_key string PEM encoded private key for server.
        @param client_ca_cert string PEM encoded CA certificate for client.
        @param client_cert string PEM encoded identity certificate for client.
        @param client_key string PEM encoded private key for client.

        """
        super(WPAEAPConfig, self).__init__(
                security='802_1x', file_suffix=file_suffix,
                use_system_cas=use_system_cas,
                server_ca_cert=server_ca_cert, server_cert=server_cert,
                server_key=server_key, client_ca_cert=client_ca_cert,
                client_cert=client_cert, client_key=client_key)


    def get_shill_service_properties(self):
        """@return dict of shill service properties."""
        return super(WPAEAPConfig, self).get_shill_service_properties()


    def get_hostapd_config(self):
        """@return dict fragment of hostapd configuration for security."""
        ret = super(WPAEAPConfig, self).get_hostapd_config()
        # If we wanted to expand test coverage to WPA2/PEAP combinations
        # or particular ciphers, we'd have to let people set these
        # settings manually.  But for now, do the simple thing.
        ret.update({'wpa': WPAConfig.MODE_PURE_WPA,
                    'wpa_pairwise': WPAConfig.CIPHER_CCMP,
                    'wpa_key_mgmt':'WPA-EAP'})
        return ret
