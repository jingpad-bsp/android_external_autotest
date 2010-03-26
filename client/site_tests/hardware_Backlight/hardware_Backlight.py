# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import utils
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

def backlight_tool(args):
    cmd = 'backlight-tool %s' % args
    return utils.system_output(cmd)

class hardware_Backlight(test.test):
    version = 1

    def run_once(self):
        try:
            brightness = int(backlight_tool("--get_brightness").rstrip())
        except error.CmdError, e:
            raise error.TestFail('Cannot get brightness with backlight-tool')
        max_brightness = int(backlight_tool("--get_max_brightness").rstrip())
        try:
            for i in range(max_brightness + 1):
                backlight_tool("--set_brightness %d" % i)
                result = int(backlight_tool("--get_brightness").rstrip())
                if i != result:
                    raise error.TestFail('Adjusting backlight should change ' \
                                         'actual brightness')
        finally:
            backlight_tool("--set_brightness %d" % brightness)
