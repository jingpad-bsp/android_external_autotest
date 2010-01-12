# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import site_power_status



class system_PowerStatus(test.test):
    version = 1


    def run_once(self):
        status = site_power_status.get_status()
        logging.info("battery_energy: %f" % status.battery[0].energy)
        logging.info("linepower_online: %s" % status.linepower[0].online)
