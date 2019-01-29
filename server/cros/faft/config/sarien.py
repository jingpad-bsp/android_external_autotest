# Copyright 2019 Google LLC
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""FAFT configuration overrides for Sarien."""

class Values(object):
    """FAFT config values for Sarien."""
    firmware_screen = 15
    delay_reboot_to_ping = 40
    hold_pwr_button_poweron = 1.2
    has_lid = True
    spi_voltage = 'pp3300'
    wp_voltage = 'pp3300'
    # Not a Chrome EC, do not expect keyboard via EC
    chrome_ec = False
    ec_capability = []
    has_keyboard = False
    # Temporary until switch to power button
    rec_button_dev_switch = True
