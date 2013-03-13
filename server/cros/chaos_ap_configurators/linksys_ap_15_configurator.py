# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Subclass of the LinksysAPConfigurator."""

import linksys_ap_configurator


class LinksysAP15Configurator(linksys_ap_configurator.LinksysAPConfigurator):
    """Derived class to control Linksys WRT54G2 1.5 router."""

    def _set_mode(self, mode):
        # Create the mode to popup item mapping
        mode_mapping = {self.mode_b: 'B-Only', self.mode_g: 'G-Only',
                        self.mode_b | self.mode_g: 'Mixed',
                        'Disabled': 'Disabled'}
        mode_name = mode_mapping.get(mode)
        if not mode_name:
            raise RuntimeError('The mode selected %d is not supported by router'
                               ' %s.', hex(mode), self.get_router_name())
        xpath = ('//select[@name="wl_net_mode"]')
        self.select_item_from_popup_by_xpath(mode_name, xpath)


    def _set_visibility(self, visible=True):
        self._set_radio(enabled=True)
        int_value = 0 if visible else 1
        xpath = ('//input[@value="%d" and @name="wl_closed"]' % int_value)
        self.click_button_by_xpath(xpath)
