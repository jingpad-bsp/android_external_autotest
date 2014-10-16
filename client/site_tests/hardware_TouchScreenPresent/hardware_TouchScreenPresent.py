# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from autotest_lib.client.bin import utils
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.graphics import graphics_utils


class hardware_TouchScreenPresent(test.test):
    '''
    Check if the maXTouch touch screen device is configured in the X system.
    '''
    version = 1

    def run_once(self):
        utils.assert_has_X_server()
        cmd = 'xinput list'
        xi_out = utils.system_output(graphics_utils.xcommand(cmd))
        if xi_out.find('maXTouch') == -1 :
            raise error.TestFail('No touch screen found')
        if not re.search('maXTouch.*floating slave', xi_out ):
            raise error.TestFail(
                    'Touch screen seems to be improperly configured')
