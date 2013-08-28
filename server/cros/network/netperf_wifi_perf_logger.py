# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging


class NetperfWiFiPerfLogger(object):
    """Delegate object to write netperf keyvals in a standard format."""

    @property
    def channel_label(self):
        """@return string like 'ch011' corresponding to configured channel."""
        return 'ch%03d' % self._ap_config.channel


    def __init__(self, ap_config, wifi_client, keyval_recorder):
        """Construct a NetperfWiFiPerfLogger.

        @param ap_config a HostapConfig object representing the state
                of the AP that netperf is being run against.
        @param wifi_client a WiFiClient representing the DUT in the test.
        @param keyval_recorder a function that takes a single argument which
                is a dict of keyvals.  For instance, this could be the
                |write_perf_keyvals| function from a test object.

        """
        self._ap_config = ap_config
        self._wifi_client = wifi_client
        self.write_perf_keyval = keyval_recorder


    def record_signal_keyval(self, descriptive_tag=None):
        """Records the current WiFi signal level as a keyval.

        @param descriptive_tag string concise whitespace free string to be
                embedded in keyval keys.

        """
        tag_pieces = [self._wifi_client.machine_id, 'signal',
                      self.channel_label]
        if descriptive_tag:
            tag_pieces.append(descriptive_tag)
        signal_level_key = '_'.join(tag_pieces)
        signal_level = self._wifi_client.wifi_signal_level
        self.write_perf_keyval({signal_level_key: signal_level})
        logging.debug('Signal level for channel %d is %d dBm',
                      self._ap_config.channel, signal_level)


    def record_keyvals_for_result(self, result, descriptive_tag=None):
        """Records result data keyvals.

        @param result NetperfResult object.
        @param descriptive_tag string concise whitespace free string to be
                embedded in keyval keys.

        """
        mode = self._ap_config.printable_mode
        mode = mode.replace('+', 'p').replace('-', 'm')
        suffix = '%s_mode%s_%s_%s' % (
                self.channel_label,
                mode,
                self._ap_config.security_config.security,
                descriptive_tag or result.tag)
        keyvals = result.get_keyval(prefix=self._wifi_client.machine_id,
                                    suffix=suffix)
        self.write_perf_keyval(keyvals)
