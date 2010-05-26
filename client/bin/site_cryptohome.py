# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, utils, time
from autotest_lib.client.bin import chromeos_constants, test
from autotest_lib.client.common_lib import error

def __get_mount_parts(expected_mountpt = chromeos_constants.CRYPTOHOME_MOUNT_PT,
                      allow_fail = False):
    mount_line = utils.system_output(
        'grep %s /proc/$(pgrep cryptohomed)/mounts' % expected_mountpt,
        ignore_status = allow_fail)
    return mount_line.split()


def is_mounted(device = chromeos_constants.CRYPTOHOME_DEVICE,
               expected_mountpt = chromeos_constants.CRYPTOHOME_MOUNT_PT,
               allow_fail = False):
    mount_parts = _get_mount_parts(device, allow_fail)
    return len(mount_parts) > 0 and device == mount_parts[0]


def is_mounted_on_tmpfs(device = chromeos_constants.CRYPTOHOME_DEVICE,
                        expected_mountpt =
                            chromeos_constants.CRYPTOHOME_MOUNT_PT,
                        allow_fail = False):
    mount_parts = __get_mount_parts(device, allow_fail)
    return (len(mount_parts) > 2 and device == mount_parts[0] and
            'tmpfs' == mount_parts[2])
