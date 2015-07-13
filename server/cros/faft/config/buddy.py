# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""FAFT configuration overrides for Buddy."""

from autotest_lib.server.cros.faft.config import auron


class Values(auron.Values):
    """Inherit overrides from auron."""
    ec_capability = ['x86', 'usb', 'smart_usb_charge']
    has_lid = False
    has_keyboard = False
    keyboard_dev = True
    rec_button_dev_switch = True
