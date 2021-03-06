# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""FAFT config setting overrides for Dragonegg."""

class Values(object):
    """FAFT config values for Dragonegg."""
    chrome_ec = True
    ec_capability = ['battery', 'charging',
                     'keyboard', 'lid', 'x86', 'usb', 'smart_usb_charge']
    firmware_screen = 15
    spi_voltage = 'pp3300'
    servo_prog_state_delay = 10
    dark_resume_capable = True
    custom_usb_enable_names = ['EN_USB_A_5V']
    smm_store = False
