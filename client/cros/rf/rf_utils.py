# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import rf_common

from autotest_lib.client.bin import utils

def SetInterfaceIp(interface, ip):
    utils.system('ifconfig %s %s' % (interface, ip))
