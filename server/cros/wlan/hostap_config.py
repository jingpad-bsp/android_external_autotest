# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error


class HostapConfig(object):
    """Parameters for router configuration."""

    # A mapping of frequency to channel number.  This includes some
    # frequencies used outside the US.
    CHANNEL_MAP = {2412: 1,
                   2417: 2,
                   2422: 3,
                   2427: 4,
                   2432: 5,
                   2437: 6,
                   2442: 7,
                   2447: 8,
                   2452: 9,
                   2457: 10,
                   2462: 11,
                   # 12, 13 are only legitimate outside the US.
                   2467: 12,
                   2472: 13,
                   # 34 valid in Japan.
                   5170: 34,
                   # 36-116 valid in the US, except 38, 42, and 46, which have
                   # mixed international support.
                   5180: 36,
                   5190: 38,
                   5200: 40,
                   5210: 42,
                   5220: 44,
                   5230: 46,
                   5240: 48,
                   5260: 52,
                   5280: 56,
                   5300: 60,
                   5320: 64,
                   5500: 100,
                   5520: 104,
                   5540: 108,
                   5560: 112,
                   5580: 116,
                   # 120, 124, 128 valid in Europe/Japan.
                   5600: 120,
                   5620: 124,
                   5640: 128,
                   # 132+ valid in US.
                   5660: 132,
                   5680: 136,
                   5700: 140,
                   5745: 149,
                   5765: 153,
                   5785: 157,
                   5805: 161,
                   5825: 165}

    MODE_11A = 'a'
    MODE_11B = 'b'
    MODE_11G = 'g'
    MODE_11N_MIXED = 'n-mixed'
    MODE_11N_PURE = 'n-only'

    N_CAPABILITY_WMM = object()
    N_CAPABILITY_HT20 = object()
    N_CAPABILITY_HT40 = object()
    N_CAPABILITY_HT40_PLUS = object()
    N_CAPABILITY_HT40_MINUS = object()
    N_CAPABILITY_GREENFIELD = object()
    N_CAPABILITY_SHORT_GI = object()

    @property
    def ht_packet_capture_mode(self):
        """Get an appropriate packet capture HT parameter.

        When we go to configure a raw monitor we need to configure
        the phy to listen on the correct channel.  Part of doing
        so is to specify the channel width for HT channels.  In the
        case that the AP is configured to be either HT40+ or HT40-,
        we could return the wrong parameter because we don't know which
        configuration will be chosen by hostap.

        @return string HT parameter for frequency configuration.

        """
        if not self.n_capabilities:
            return None

        is_plus = '[HT40+]' in self.n_capabilities
        is_minus = '[HT40-]' in self.n_capabilities
        if is_plus and is_minus:
            # TODO(wiley) Apparently, for some channels, there are regulatory
            #             rules for which side of the channel you may use with
            #             HT40 mode.  For some channels, HT40 is disabled
            #             altogether.
            logging.warning('Packet capture may fail because both HT40+ and '
                            'HT40- enabled.  hostap will choose one or the '
                            'other, but we do not know that decision.')
            return 'HT40-'

        if is_plus:
            return 'HT40+'

        if is_minus:
            return 'HT40-'

        return 'HT20'


    def __init__(self, mode=None, channel=None, frequency=None,
                 n_capabilities=None, hide_ssid=None, beacon_interval=None,
                 dtim_period=None, frag_threshold=None, ssid=None, bssid=None,
                 force_wmm=None):
        """Construct a HostapConfig.

        You may specify channel or frequency, but not both.  Both options
        are checked for validity (i.e. you can't specify an invalid channel
        or a frequency that will not be accepted).

        @param mode string MODE_11x defined above.
        @param channel int channel number.
        @param frequency int frequency of channel.
        @param n_capabilities list of N_CAPABILITY_x defined above.
        @param hide_ssid True if we should set up a hidden SSID.
        @param beacon_interval int beacon interval of AP.
        @param dtim_period int include a DTIM every |dtim_period| beacons.
        @param frag_threshold int maximum outgoing data frame size.
        @param ssid string up to 32 byte SSID overriding the router default.
        @param bssid string like 00:11:22:33:44:55.
        @param force_wmm True if we should force WMM on, False if we should
            force it off, None if we shouldn't force anything.


        """
        super(HostapConfig, self).__init__()
        if channel is not None and frequency is not None:
            raise error.TestError('Specify either frequency or channel '
                                  'but not both.')

        if channel is None and frequency is None:
            raise error.TestError('Specify either frequency or channel.')

        for real_frequency, real_channel in self.CHANNEL_MAP.iteritems():
            if frequency == real_frequency or channel == real_channel:
                self.frequency = real_frequency
                self.channel = real_channel
                break
        else:
            raise error.TestError('Invalid channel %r or frequency %r '
                                  'specified.' % channel, frequency)

        self.is_11n = False
        self.require_ht = False
        if mode in (self.MODE_11N_MIXED, self.MODE_11N_PURE) or n_capabilities:
            if mode == self.MODE_11N_PURE:
                # TODO(wiley) Why? (crbug.com/237370)
                logging.warning('Not enforcing pure N mode because Snow does '
                                'not seem to support it...')
                #self.require_ht = True
            # For their own historical reasons, hostapd wants it this way.
            if self.frequency > 5000:
                mode = self.MODE_11A
            else:
                mode = self.MODE_11G
            self.is_11n = True
        if self.frequency > 5000 and mode != self.MODE_11A:
            raise error.TestError('Must use 11a or 11n mode for '
                                  'frequency > 5Ghz')

        if self.frequency < 5000 and mode == self.MODE_11A:
            raise error.TestError('Cannot use 11a with frequency %d.' %
                                  self.frequency)

        if not mode in (self.MODE_11A, self.MODE_11B, self.MODE_11G, None):
            raise error.TestError('Invalid router mode %r' % mode)

        self.wmm_enabled = False
        self.hw_mode = mode or self.MODE_11B
        self.ssid_suffix = '_ch%d' % self.channel
        if n_capabilities is None:
            n_capabilities = []
        self.n_capabilities = set()
        for cap in n_capabilities:
            if cap == self.N_CAPABILITY_HT40:
                self.wmm_enabled = True
                self.n_capabilities.add('[HT40-]')
                self.n_capabilities.add('[HT40+]')
            elif cap == self.N_CAPABILITY_HT40_PLUS:
                self.wmm_enabled = True
                self.n_capabilities.add('[HT40+]')
            elif cap == self.N_CAPABILITY_HT40_MINUS:
                self.wmm_enabled = True
                self.n_capabilities.add('[HT40-]')
            elif cap == self.N_CAPABILITY_GREENFIELD:
                logging.warning('Greenfield flag is ignored for hostap...')
                #TODO(wiley) Why does this not work?
                #self.n_capabilities.add('[GF]')
            elif cap == self.N_CAPABILITY_SHORT_GI:
                self.n_capabilities.add('[SHORT-GI-20]')
                self.n_capabilities.add('[SHORT-GI-40]')
            elif cap == self.N_CAPABILITY_HT20:
                # This isn't a real thing.  HT mode implies 20 supported.
                self.wmm_enabled = True
            elif cap == self.N_CAPABILITY_WMM:
                self.wmm_enabled = True
            else:
                raise error.TestError('Unknown capability: %r' % cap)

        self.hide_ssid = hide_ssid
        self.beacon_interval = beacon_interval
        self.dtim_period = dtim_period
        self.frag_threshold = frag_threshold
        if ssid and len(ssid) > 32:
            raise error.TestFail('Tried to specify SSID that was too long.')

        self.ssid = ssid
        self.bssid = bssid
        if force_wmm is not None:
            self.wmm_enabled = force_wmm
