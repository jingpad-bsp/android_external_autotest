# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# The names of expected mount-points, devices, magic files, etc on chrome os.

# Constants used by other constants.
USER_DATA_DIR = '/home/chronos'
WHITELIST_DIR = '/var/lib/whitelist'


# Rest of constants.
BROWSER = 'chrome'
BROWSER_EXE = '/opt/google/chrome/' + BROWSER

CHROME_LOG_DIR = '/var/log/chrome'
CHROME_WINDOW_MAPPED_MAGIC_FILE = \
    '/var/run/state/windowmanager/initial-chrome-window-mapped'

CLEANUP_LOGS_PAUSED_FILE = '/var/lib/cleanup_logs_paused'

CLIENT_LOGIN_URL = '/accounts/ClientLogin'

CREDENTIALS = {
    '$default': ['performance.test.account@gmail.com', 'perfsmurf'],
    '$apps': ['performance.test.account@googleapps.com', 'perfsmurf'],
    '$backdoor': ['chronos@gmail.com', 'chronos'],
}

# TODO(fes): With the switch to ecryptfs, the cryptohome device is no longer
# static--it includes a system-specific hash of the username whose vault is
# mounted.  seano points out that this is no longer a constant, and we may want
# to change the way tests dependent on this value work.
CRYPTOHOME_DEVICE_REGEX = r'^/home/\.shadow/.*/vault$'
CRYPTOHOME_INCOGNITO = 'guestfs'
CRYPTOHOME_MOUNT_PT = USER_DATA_DIR + '/user'

CRYPTOHOMED_LOG = '/var/log/cryptohomed.log'

DISABLE_BROWSER_RESTART_MAGIC_FILE = '/tmp/disable_chrome_restart'

FLIMFLAM_TEST_PATH = '/usr/lib/flimflam/test/'

KEYGEN = 'keygen'

LOGGED_IN_MAGIC_FILE = '/var/run/state/logged-in'

LOGIN_PROFILE = USER_DATA_DIR + '/Default'
LOGIN_SERVICE = 'gaia'
LOGIN_ERROR = 'Error=BadAuthentication'
LOGIN_PROMPT_READY_MAGIC_FILE = '/tmp/uptime-login-prompt-ready'
LOGIN_TRUST_ROOTS = '/etc/login_trust_root.pem'

ISSUE_AUTH_TOKEN_URL = '/accounts/IssueAuthToken'

OWNER_KEY_FILE = WHITELIST_DIR+'/owner.key'

SESSION_MANAGER = 'session_manager'
SESSION_MANAGER_LOG = '/var/log/session_manager'
SIGNED_PREFERENCES_FILE = WHITELIST_DIR+'/preferences'
SPECIAL_CASE_DOMAIN = 'gmail.com'

TOKEN_AUTH_URL = '/accounts/TokenAuth'

UI_LOG = '/var/log/ui/ui.LATEST'
UPDATE_ENGINE_LOG = '/var/log/update_engine.log'

WINDOW_MANAGER = 'chromeos-wm'
