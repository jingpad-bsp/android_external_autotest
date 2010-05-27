# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# The names of expected mount-points, devices, magic files, etc on chrome os.

USER_DATA_DIR = '/home/chronos'

LOGIN_PROFILE = USER_DATA_DIR+'/Default'

# TODO(fes): With the switch to ecryptfs, the cryptohome device is no longer
# static--it includes a system-specific hash of the username whose vault is
# mounted.  seano points out that this is no longer a constant, and we may want
# to change the way tests dependent on this value work.
CRYPTOHOME_DEVICE_REGEX = r'^/home/\.shadow/.*/vault$'
CRYPTOHOME_INCOGNITO = 'incognito'
CRYPTOHOME_MOUNT_PT = USER_DATA_DIR+'/user'

LOGIN_TRUST_ROOTS = '/etc/login_trust_root.pem'

BROWSER = 'chrome'
SESSION_MANAGER = 'session_manager'
WINDOW_MANAGER = 'chromeos-wm'

LOGGED_IN_MAGIC_FILE = '/var/run/state/logged-in'

CHROME_WINDOW_MAPPED_MAGIC_FILE = \
    '/var/run/state/windowmanager/initial-chrome-window-mapped'

DISABLE_BROWSER_RESTART_MAGIC_FILE = '/tmp/disable_chrome_restart'

CREDENTIALS = {
    '$default': ['performance.test.account@gmail.com', 'perfsmurf'],
    '$backdoor': ['chronos@gmail.com', 'chronos'],
}

CLIENT_LOGIN_URL = '/accounts/ClientLogin'
ISSUE_AUTH_TOKEN_URL = '/accounts/IssueAuthToken'
TOKEN_AUTH_URL = '/accounts/TokenAuth'
