# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""FAFT config setting overrides for Rambi."""


class Values(object):
    """FAFT config values for Rambi."""
    firmware_screen = 7
    dev_screen = 7
    chrome_ec = True
    long_rec_combo = True
    ec_capability = ['battery', 'charging', 'keyboard', 'lid', 'x86',
                     'usb', 'smart_usb_charge']
    wp_voltage = 'pp1800'
