# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error, site_ui

class hardware_UsbPlugIn(test.test):
    version = 1

    def run_once(self):
        cmd = 'lsusb | sed "s/.*ID ....:.... //"'
        original_usbs = utils.system_output(cmd).split('\n')

        dialog = site_ui.Dialog(question="Please plug a USB device in.",
                                choices=["OK"])
        result = dialog.get_result()
        plugin_usbs = utils.system_output(cmd).split('\n')
        new_usbs = [e for e in plugin_usbs if e not in original_usbs]

        if not new_usbs:
            raise error.TestFail("No USB device detected after plugging in");

        dialog.init(question="Detected:<br>%s.<hr>Please unplug the device." %
                    ", <br>".join(new_usbs), choices=["OK"])
        result = dialog.get_result()

        unplug_usbs = utils.system_output(cmd).split('\n')
        if original_usbs != unplug_usbs:
            raise error.TestFail("The USB devices are not the same as before "
                                 "after unplugging");
