# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""FAFT config setting overrides for Veyron."""


class Values(object):
    """FAFT config values for Veyron."""
    software_sync_update = 6
    chrome_ec = True
    ec_capability = ['battery', 'charging', 'keyboard', 'arm', 'lid']
    ec_boot_to_console = 1.1
    wp_voltage = 'pp3300'
