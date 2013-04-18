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


    def __init__(self, mode=None, channel=None, frequency=None,
                 n_capabilities=None, hide_ssid=None):
        """Construct a HostapConfig.

        You may specify channel or frequency, but not both.  Both options
        are checked for validity (i.e. you can't specify an invalid channel
        or a frequency that will not be accepted).

        @param mode string MODE_11x defined above.
        @param channel int channel number.
        @param frequency int frequency of channel.
        @param n_capabilities list of N_CAPABILITY_x defined above.
        @param hide_ssid True if we should set up a hidden SSID.

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
                self.require_ht = True
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
