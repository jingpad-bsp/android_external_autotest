# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# The names of expected mount-points, devices, magic files, etc on chrome os.

USER_DATA_DIR = '/home/chronos'

LOGIN_PROFILE = USER_DATA_DIR+'/Default'

CRYPTOHOME_DEVICE = '/dev/mapper/cryptohome'
CRYPTOHOME_MOUNT_PT = USER_DATA_DIR+'/user'

BROWSER = 'chrome'

LOGGED_IN_MAGIC_FILE = '/var/run/state/logged-in'

DISABLE_BROWSER_RESTART_MAGIC_FILE = '/tmp/disable_chrome_restart'
