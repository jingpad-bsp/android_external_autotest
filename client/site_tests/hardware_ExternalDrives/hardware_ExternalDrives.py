# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, re

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui, cros_ui_test


class hardware_ExternalDrives(cros_ui_test.UITest):
    version = 1

    @staticmethod
    def _find_root_dev():
        rootdev = utils.system_output('rootdev -s -d')
        return os.path.basename(rootdev)


    @staticmethod
    def _find_all_storage_dev():
        lssys = utils.run('ls -d /sys/block/sd*')
        devices = lssys.stdout.rsplit('\n')
        new_devices = [os.path.basename(d.rstrip()) for d in devices if d]
        return new_devices


    def run_once(self):
        num_retry = 3
        dialog = cros_ui.Dialog(question=("Please insert a USB flash drive and "
            "a SD-card. Then press the RETRY button."), choices=['RETRY'])

        while num_retry:
            # Find all block devices in the system.
            devices = self._find_all_storage_dev()
            devices.remove(self._find_root_dev())

            if len(devices) >= 2:
                # For each device, run the whole test suite.
                for device in devices:
                    devpath = '/dev/' + device
                    if os.path.exists(devpath):
                        self.job.run_test('hardware_StorageFio', dev=devpath,
                                     tag=device)
                break
            else:
                result = dialog.get_result()
                num_retry -= 1;

        else:
            raise error.TestError('Unable to find a USB flash drive and '
                                  'a SD-card')


