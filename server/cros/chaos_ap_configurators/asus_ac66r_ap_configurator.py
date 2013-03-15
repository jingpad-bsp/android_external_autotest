# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import asus_qis_ap_configurator


class Asus66RAPConfigurator(asus_qis_ap_configurator.AsusQISAPConfigurator):
    """Derives class for Asus RT-AC66R."""


    def _set_channel(self, channel):
        position = self._get_channel_popup_position(channel)
        channel_choices = ['Auto', '01', '02', '03', '04', '05', '06',
                           '07', '08', '09', '10', '11']
        xpath = '//select[@name="wl_chanspec"]'
        if self.current_band == self.band_5ghz:
            channel_choices = ['Auto', '36', '40', '44', '48', '149', '153',
                               '157', '161']
        self.select_item_from_popup_by_xpath(str(channel_choices[position]),
                                             xpath)
