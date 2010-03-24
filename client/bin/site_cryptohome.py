# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, utils, time
from autotest_lib.client.bin import chromeos_constants, test
from autotest_lib.client.common_lib import error

def is_mounted(device = chromeos_constants.CRYPTOHOME_DEVICE,
               expected_mountpt = chromeos_constants.CRYPTOHOME_MOUNT_PT,
               allow_fail = False):
    mount_line = utils.system_output('/bin/mount | grep %s' % expected_mountpt,
                                     ignore_status = allow_fail)
    mount_parts = mount_line.split()
    return len(mount_parts) > 0 and device == mount_parts[0]
