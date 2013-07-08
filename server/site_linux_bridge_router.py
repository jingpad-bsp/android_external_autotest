# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, re, time
from autotest_lib.client.common_lib import error
from autotest_lib.server import site_linux_router

class LinuxBridgeRouter(site_linux_router.LinuxRouter):
    """
    Linux/mac80211-style WiFi Router support for WiFiTest class.

    As compared to LinuxRouter, LinuxBridgeRouter adds support for
    bridging. Specifically: the wireless and wired interfaces are
    bridged together.
    """


    def __init__(self, host, params, defssid):
        site_linux_router.LinuxRouter.__init__(self, host, params, defssid)

        self.bridgeif = params.get('bridgedev', "br-lan")
        self.wiredif = params.get('wiredev', "eth0")
        self.cmd_brctl = "/usr/sbin/brctl"

        self.hostapd['conf']['bridge'] = self.bridgeif
        self.default_config['bridge'] = self.bridgeif

        # Remove all bridges.
        output = self.router.run("%s show" % self.cmd_brctl).stdout
        test = re.compile("^(\S+).*")
        for line in output.splitlines()[1:]:
            m = test.match(line)
            if m:
                device = m.group(1)
                self.router.run("%s link set %s down" % (self.cmd_ip, device))
                self.router.run("%s delbr %s" % (self.cmd_brctl, device))


    def _pre_start_hook(self, params):
        if 'multi_interface' not in params:
            logging.info("Initializing bridge...")
            self.router.run("%s addbr %s" %
                            (self.cmd_brctl, self.bridgeif))
            self.router.run("%s setfd %s %d" %
                            (self.cmd_brctl, self.bridgeif, 0))
            self.router.run("%s stp %s %d" %
                            (self.cmd_brctl, self.bridgeif, 0))


    def _post_start_hook(self, params):
        if 'multi_interface' not in params:
            logging.info("Setting up the bridge...")
            self.router.run("%s addif %s %s" %
                            (self.cmd_brctl, self.bridgeif, self.wiredif))
            self.router.run("%s link set %s up" %
                            (self.cmd_ip, self.wiredif))
            self.router.run("%s link set %s up" %
                            (self.cmd_ip, self.bridgeif))


    def deconfig(self, params={}):
        """ De-configure the AP (will also bring wlan and the bridge down) """

        site_linux_router.LinuxRouter.deconfig(self, params)

        # Try a couple times to remove the bridge; hostapd may still be exiting
        for attempt in range(3):
            self.router.run("%s link set %s down" %
                            (self.cmd_ip, self.bridgeif), ignore_status=True)

            result = self.router.run("%s delbr %s" %
                                     (self.cmd_brctl, self.bridgeif),
                                     ignore_status=True)
            if not result.stderr or 'No such device' in result.stderr:
                break
            time.sleep(1)
        else:
            raise error.TestFail("Unable to delete bridge %s: %s" %
                                 (self.bridgeif, result.stderr))
