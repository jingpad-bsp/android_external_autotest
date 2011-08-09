# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, re, time
from autotest_lib.client.common_lib import error
from autotest_lib.server import site_linux_system
from autotest_lib.server import site_linux_router

class LinuxVMRouter(site_linux_router.LinuxRouter):
    """
    Linux/mac80211-style WiFi Router support for WiFiTest class.

    As compared to LinuxRouter, LinuxVMRouter is specialized for routers
    running a ChromiumOS image.
    """

    def __init__(self, host, params, defssid):
        host.run("rmmod mac80211_hwsim", ignore_status=True)
        host.run("modprobe mac80211_hwsim radios=3")

        site_linux_router.LinuxRouter.__init__(
            self, host, params, defssid)

        # Override LinuxSystem's phy assignment.
        self.phy_for_frequency = {}
        phy_infos = host.run("%s list" % self.cmd_iw).stdout.splitlines()
        phy_list = \
            [phy_info.split()[1] for phy_info in phy_infos \
               if phy_info.startswith('Wiphy')]

        # In the VM case, the client runs on the same node as the router.
        # Since LinuxRouter.__init__ removes all interfaces, we need to
        # set up a device for the client. [quiche.20110823]
        client_phy = phy_list[0]
        host.run("%s phy %s interface add client0 type managed" %
                 (self.cmd_iw, client_phy))

        # Both remaining virtual devices are dual-band. Arbitrarily
        # assign one to 2.4 GHz, and the other to 5 GHz.
        self.phydev2 = self.phydev2 or phy_list[1]
        self.phydev5 = self.phydev5 or phy_list[2]


    def _pre_config_hook(self, config):
        # kludge for hostapd 0.6.9 and earlier [quiche.20110808]
        if 'wmm_enabled' in config:
            del config['wmm_enabled']
