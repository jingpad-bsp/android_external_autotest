# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
You must have the 53d0a92e9b0b37daebc795cc1ea4684d1c0dffd8 from
chromeos/master to have the necessary configuration changes to the
openwrt repository.  You must then build the 'rspro' variant and
upgrade your router with the new firmware to be able to run this test.

You must build the 'rspro' openwrt variant with these configuration
changes, and update the rspro router to the newly built firmware to be
able to run this test.

This test starts & verfies a VPN connection from the Client (DUT) to
the Server (rspro).
"""

from autotest_lib.server import site_wifitest

class network_VPN(site_wifitest.test):
      pass
