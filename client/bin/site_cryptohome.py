# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, utils, time
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

def is_mounted(device = '/dev/mapper/cryptohome',
               expected_mountpt = '/home/chronos/user'):
    mount_line = utils.system_output('/bin/mount | grep %s' % device)
    mountpt = (mount_line.split())[2]
    return expected_mountpt == mountpt
