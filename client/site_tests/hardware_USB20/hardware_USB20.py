# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob, re

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error, site_ui

class hardware_USB20(test.test):
    version = 1

    def run_once(self):
        # 'lsusb' gives a bunch of USB device lines like:
        # Bus 001 Device 009: ID 0930:6544 Toshiba Corp. Kingston DataTravel...
        # The bus and device fields are at [1] and [3].
        cmd = 'lsusb'
        original_lsusb = utils.system_output(cmd).split('\n')

        dialog = site_ui.Dialog(question="Please plug a USB 2.0 device in.",
                                choices=["OK"])
        result = dialog.get_result()
        plugin_lsusb = utils.system_output(cmd).split('\n')
        new_lsusb = [e for e in plugin_lsusb if e not in original_lsusb]

        if not new_lsusb:
            raise error.TestFail("No USB device detected after plugging in");

        # For each new device, find its bus and device fields and verify 2.0.
        for usb_dev in new_lsusb:
            usb_version = "unknown"
            bus = usb_dev.split(' ')[1]
            dev = usb_dev.split(' ')[3]

            # 'lsusb -s BUS:DEV -v' gives verbose output including at least one
            # bcdUSB line which describes its USB version.  Confirm 2.0.
            verbose_cmd = "lsusb -s %s:%s -v" % (bus, dev)
            linesout = utils.system_output(verbose_cmd).split('\n')
            for line in linesout:
                version_pattern = re.search(r' *bcdUSB *([^ ]+)', line)
                if version_pattern:
                    usb_version = version_pattern.group(1)
                    break

            if usb_version != "2.00":
                raise error.TestFail("usb_dev %s gives version %s" %
                                     (usb_dev, usb_version))

        dialog.init(question="Detected:<br>%s.<hr>Please unplug the device." %
                    ", <br>".join(new_lsusb), choices=["OK"])
        result = dialog.get_result()

        unplug_lsusb = utils.system_output(cmd).split('\n')
        if original_lsusb != unplug_lsusb:
            raise error.TestFail("The USB devices are not the same as before "
                                 "after unplugging")
