# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.client.common_lib.cros.network import xmlrpc_security_types

# Supported bands
BAND_2GHZ = '2.4GHz'
BAND_5GHZ = '5GHz'

# List of valid bands.
VALID_BANDS = [BAND_2GHZ, BAND_5GHZ]

# List of valid 802.11 protocols (modes).
MODE_A = 0x01
MODE_B = 0x02
MODE_G = 0x04
MODE_N = 0x08
MODE_AUTO = 0x10
MODE_M = MODE_A | MODE_B | MODE_G # Used for standard maintenance
MODE_D = MODE_A | MODE_B | MODE_N # International roaming extensions

# List of valid modes.
VALID_MODES = [MODE_A, MODE_AUTO, MODE_B, MODE_D, MODE_G, MODE_M, MODE_N]
VALID_2GHZ_MODES = [MODE_B, MODE_G, MODE_N]
VALID_5GHZ_MODES = [MODE_A, MODE_N]

# Supported security types
SECURITY_TYPE_DISABLED = 'disabled'
SECURITY_TYPE_WEP = 'wep'
SECURITY_TYPE_WPAPSK = 'wpa-psk'
SECURITY_TYPE_WPA2PSK = 'wpa2-psk'

WEP_AUTHENTICATION_OPEN = 'open'
WEP_AUTHENTICATION_SHARED = 'shared'

# List of valid securities.
# TODO (krisr) the configurators do not support WEP at this time.
VALID_SECURITIES = [SECURITY_TYPE_DISABLED,
                    SECURITY_TYPE_WPAPSK,
                    SECURITY_TYPE_WPA2PSK]

# List of valid channels.
VALID_2GHZ_CHANNELS = range(1,15)
VALID_5GHZ_CHANNELS = [36, 40, 44, 48, 149, 153, 157, 161, 165]

# Default values
DEFAULT_BAND = BAND_2GHZ

DEFAULT_2GHZ_MODE = MODE_G
DEFAULT_5GHZ_MODE = MODE_A

DEFAULT_SECURITY_TYPE = SECURITY_TYPE_DISABLED

DEFAULT_2GHZ_CHANNEL = 5
DEFAULT_5GHZ_CHANNEL = 149

# Convenience method to convert modes to human readable strings.
def mode_string_for_mode(mode):
    """
    Returns a human readable string of the mode.

    @param mode: integer, the mode to convert.
    @returns: string representation of the mode
    """
    string_table = {MODE_A:'a', MODE_B:'b', MODE_G:'g', MODE_N:'n'}

    if mode == MODE_AUTO:
        return 'Auto'
    total = 0
    string = ''
    for current_mode in sorted(string_table.keys()):
        i = current_mode & mode
        total = total | i
        if i in string_table:
            string = string + string_table[i] + '/'
    if total == MODE_M:
        string = 'm'
    elif total == MODE_D:
        string = 'd'
    if string[-1] == '/':
        return string[:-1]
    return string


class APSpec(object):
    """Object to specify an APs desired capabilities.

    The APSpec object is immutable.  All of the parameters are optional.
    For those not given the defaults listed above will be used.  Validation
    is done on the values to make sure the spec created is valid.  If
    validation fails a ValueError is raised.

    The exception for this is the unique_id member.  There is no validation
    done on this string.  It can be used by the called to easily identify an
    APSpec instance.
    """


    def __init__(self, visible=True, security=SECURITY_TYPE_DISABLED,
                 band=None, mode=None, channel=None, unique_id=None):
        super(APSpec, self).__init__()
        self._visible = visible
        self._security = security
        self._mode = mode
        self._channel = channel

        if not self._channel and not self._mode:
            if band == BAND_2GHZ or not band:
                self._channel = DEFAULT_2GHZ_CHANNEL
                self._mode = DEFAULT_2GHZ_MODE
            elif band == BAND_5GHZ:
                self._channel = DEFAULT_5GHZ_CHANNEL
                self._mode = DEFAULT_5GHZ_MODE
            else:
                raise ValueError('Invalid Band.')

        self._validate_channel_and_mode()

        if ((band == BAND_2GHZ and self._mode not in VALID_2GHZ_MODES) or
            (band == BAND_5GHZ and self._mode not in VALID_5GHZ_MODES)):
            raise ValueError('Conflicting band and modes/channels.')

        self._validate_security()

        self._unique_id = unique_id

        if not self._unique_id:
            self._unique_id = 'ap'
            unique_id_string = 'ap'
        else:
            unique_id_string = (
                self._unique_id.replace(' ', '_').replace('.', '_'))
        band_string = self.band.replace('.', '_')
        self._ssid = str('%s_%s_%s_%d_%s' % (unique_id_string, band_string,
                         mode_string_for_mode(self._mode),
                         self._channel, self._security))


    def __str__(self):
        return ('AP Specification:\n'
                'visible=%r\n'
                'security=%s\n'
                'band=%s\n'
                'mode=%s\n'
                'channel=%d\n'
                'unique_id=%s\n'
                'ssid=%s\n'
                'password=%s\n' % (self._visible, self._security, self._band,
                mode_string_for_mode(self._mode), self._channel,
                self._unique_id, self._ssid, self._password))


    @property
    def password(self):
        """Returns the password for password supported secured networks."""
        return self._password


    @property
    def ssid(self):
        """Returns the SSID for the AP."""
        return self._ssid


    @property
    def visible(self):
        """Returns if the SSID is visible or not."""
        return self._visible


    @property
    def security(self):
        """Returns the type of security."""
        return self._security


    @property
    def band(self):
        """Return the band."""
        if self._channel in VALID_2GHZ_CHANNELS:
            return BAND_2GHZ
        return BAND_5GHZ


    @property
    def mode(self):
        """Return the mode."""
        return self._mode


    @property
    def channel(self):
        """Return the channel."""
        return self._channel


    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id


    @property
    def association_parameters(self):
        """Returns the AssociationParameters equivalent for the APSpec."""
        security_config = None
        if self._security == SECURITY_TYPE_WPAPSK:
            # Not all of this is required but doing it just in case.
            security_config = xmlrpc_security_types.WPAConfig(
                psk=self._password,
                wpa_mode=xmlrpc_security_types.WPAConfig.MODE_MIXED_WPA,
                wpa_ciphers=[xmlrpc_security_types.WPAConfig.CIPHER_CCMP,
                             xmlrpc_security_types.WPAConfig.CIPHER_TKIP],
                wpa2_ciphers=[xmlrpc_security_types.WPAConfig.CIPHER_CCMP])
        return xmlrpc_datatypes.AssociationParameters(
                ssid=self._ssid, security_config=security_config,
                is_hidden=not self._visible)


    def _validate_channel_and_mode(self):
        """Validates the channel and mode selected are correct.

        raises ValueError: if the channel or mode selected is invalid
        """
        if self._channel and self._mode:
            if ((self._channel in VALID_2GHZ_CHANNELS and
                 self._mode not in VALID_2GHZ_MODES) or
                (self._channel in VALID_5GHZ_CHANNELS and
                 self._mode not in VALID_5GHZ_MODES)):
                raise ValueError('Conflicting mode/channel has been selected.')
        elif self._channel:
            if self._channel in VALID_2GHZ_CHANNELS:
                self._mode = DEFAULT_2GHZ_MODE
            elif self._channel in VALID_5GHZ_CHANNELS:
                self._mode = DEFAULT_5GHZ_MODE
            else:
                raise ValueError('Invalid channel passed.')
        else:
            if self._mode in VALID_2GHZ_MODES:
                self._channel = DEFAULT_2GHZ_CHANNEL
            elif self._mode in VALID_5GHZ_MODES:
                self._channel = DEFAULT_5GHZ_CHANNEL
            else:
                raise ValueError('Invalid mode passed.')


    def _validate_security(self):
        """Sets a password for security settings that need it.

        raises ValueError: if the security setting passed is invalid.
        """
        if self._security == SECURITY_TYPE_DISABLED:
            self._password = None
        elif (self._security == SECURITY_TYPE_WPAPSK or
             self._security == SECURITY_TYPE_WPA2PSK):
             self._password = 'chromeos'
        else:
            raise ValueError('Invalid security passed.')
