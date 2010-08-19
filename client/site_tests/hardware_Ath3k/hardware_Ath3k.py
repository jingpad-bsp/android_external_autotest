# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


def usb_device_present(vendor_device):
    '''Check if lsusb recognizes a certain vendor/device ID combination.

    This should eventually be added to autotest_lib.client.bin.utils.
    '''

    command = '/usr/sbin/lsusb -d %s' % vendor_device.lower()
    return utils.run(command).exit_status == 0


class hardware_Ath3k(test.test):
    version = 1

    def run_once(self):
        device = '0cf3:3002'
        module = 'ath3k'
        if not usb_device_present(device):
            raise error.TestFail('usb device %s not found' % device)

        if not utils.module_is_loaded(module):
            raise error.TestFail('driver module %s not loaded' % module)
