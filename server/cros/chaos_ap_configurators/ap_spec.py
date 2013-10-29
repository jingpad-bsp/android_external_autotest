# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server.cros.network import iw_runner

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
SECURITY_TYPE_DISABLED = iw_runner.SECURITY_OPEN
SECURITY_TYPE_WEP = iw_runner.SECURITY_WEP
SECURITY_TYPE_WPAPSK = iw_runner.SECURITY_WPA
SECURITY_TYPE_WPA2PSK = iw_runner.SECURITY_WPA2
# Mixed mode security is wpa/wpa2
SECURITY_TYPE_MIXED = iw_runner.SECURITY_MIXED

WEP_AUTHENTICATION_OPEN = 'open_wep'
WEP_AUTHENTICATION_SHARED = 'shared_wep'

# List of valid securities.
# TODO (krisr) the configurators do not support WEP at this time.
VALID_SECURITIES = [SECURITY_TYPE_DISABLED,
                    SECURITY_TYPE_WPAPSK,
                    SECURITY_TYPE_WPA2PSK]

# List of valid channels.
VALID_2GHZ_CHANNELS = range(1,15)
VALID_5GHZ_CHANNELS = [36, 40, 44, 48, 149, 153, 157, 161, 165]

# Frequency to channel conversion table
CHANNEL_TABLE = {2412: 1, 2417: 2, 2422: 3,
                 2427: 4, 2432: 5, 2437: 6,
                 2442: 7, 2447: 8, 2452: 9,
                 2457: 10, 2462: 11, 2467: 12,
                 2472: 13, 2484: 14, 5180: 36,
                 5200: 40, 5220: 44, 5240: 48,
                 5745: 149, 5765: 153, 5785: 157,
                 5805: 161, 5825: 165}

# This only works because the frequency table is one to one
# for channels/frequencies.
FREQUENCY_TABLE = dict((v,k) for k,v in CHANNEL_TABLE.iteritems())

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
    """


    def __init__(self, visible=True, security=SECURITY_TYPE_DISABLED,
                 band=None, mode=None, channel=None, hostnames=None):
        super(APSpec, self).__init__()
        self._visible = visible
        self._security = security
        self._mode = mode
        self._channel = channel
        self._hostnames = hostnames

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


    def __str__(self):
        return ('AP Specification:\n'
                'visible=%r\n'
                'security=%s\n'
                'band=%s\n'
                'mode=%s\n'
                'channel=%d\n'
                'password=%s' % (self._visible, self._security, self.band,
                mode_string_for_mode(self._mode), self._channel,
                self._password))


    @property
    def password(self):
        """Returns the password for password supported secured networks."""
        return self._password



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
    def frequency(self):
        """Return the frequency equivalent of the channel."""
        return FREQUENCY_TABLE[self._channel]


    @property
    def hostnames(self):
        """Return the hostnames; this may be None."""
        return self._hostnames


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
