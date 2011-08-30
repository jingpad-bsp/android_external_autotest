# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from autotest_lib.client.bin import utils
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error


class hardware_TouchScreenPresent(test.test):
    '''
    Check if the maXTouch touch screen device is configured in the X system.
    '''
    version = 1

    def run_once(self):
        xauth_path = '/home/chronos/.Xauthority'
        cmd = 'DISPLAY=:0.0 XAUTHORITY=%s xinput list' % xauth_path
        xi_out = utils.system_output(cmd)
        if xi_out.find('maXTouch') == -1 :
            raise error.TestFail('No touch screen found')
        if not re.search('maXTouch.*floating slave', xi_out ):
            raise error.TestFail(
                    'Touch screen seems to be improperly configured')
