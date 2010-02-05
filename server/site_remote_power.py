# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, urllib

remote_switch1 = '172.22.70.186'

remote_power_switch_machines = {
    'hostfoo' : {'power_ip': 'switchbar_ip', 'power_port': 'switchbar_port'},
    '172.22.71.47' : {'power_ip': remote_switch1, 'power_port': 61},
}

# factory function for choosing which remote power class to
# return
def RemotePower(host):
   if host in remote_power_switch_machines:
        return RemotePowerSwitch(remote_power_switch_machines[host])

   return None


class RemotePowerSwitch(object):
    """
    This class implements power control for the remotepowerswitch box.
    """

    def __init__(self, dict):
        self.dict = dict
        self.cmd_url = 'http://admin:12345678@%s/Set.cmd?CMD=' % (
                   dict['power_ip'])
        

    def _set_power(self, state):
        set_power_url = '%sSetPower&P%s=%s' % (self.cmd_url,
                         self.dict['power_port'], state)
        logging.info(set_power_url)

        f = urllib.urlopen(set_power_url)
        f.read()


    def set_power_on(self):
        self._set_power(1)


    def set_power_off(self):
        self._set_power(0)

