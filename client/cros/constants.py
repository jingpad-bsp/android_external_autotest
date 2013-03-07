# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# The names of expected mount-points, devices, magic files, etc on chrome os.

# Constants used by other constants.
USER_DATA_DIR = '/home/chronos'
WHITELIST_DIR = '/var/lib/whitelist'
LOG_DIR = '/var/log'

# Rest of constants.
BROWSER = 'chrome'
BROWSER_EXE = '/opt/google/chrome/' + BROWSER

CHAPS_USER_DATABASE_PATH = '/home/chronos/user/.chaps/database'

CHROME_CORE_MAGIC_FILE = '/mnt/stateful_partition/etc/collect_chrome_crashes'
CHROME_LOG_DIR = '/var/log/chrome'

CLEANUP_LOGS_PAUSED_FILE = '/var/lib/cleanup_logs_paused'

CLIENT_LOGIN_URL = '/accounts/ClientLogin'
CLIENT_LOGIN_NEW_URL = '/ClientLogin'

CRASH_DIR = '/var/spool/crash'
CRASH_REPORTER_RESIDUE_DIR = '/tmp/crash_reporter'

CREDENTIALS = {
    '$mockowner': ['mockowner.test.account@gmail.com', 'perfsmurf'],
    '$default': ['performance.test.account@gmail.com', 'perfsmurf'],
    '$apps': ['performance.test.account@googleapps.com', 'perfsmurf'],
    '$backdoor': ['chronos@gmail.com', 'chronos'],
}

SHADOW_ROOT = '/home/.shadow'

CRYPTOHOME_DEV_REGEX_ANY = r'.*'
CRYPTOHOME_DEV_REGEX_REGULAR_USER_SHADOW = r'^/home/\.shadow/.*/vault$'
CRYPTOHOME_DEV_REGEX_REGULAR_USER_EPHEMERAL = r'^ephemeralfs/.*$'
CRYPTOHOME_DEV_REGEX_REGULAR_USER = r'(%s|%s)' % (
    CRYPTOHOME_DEV_REGEX_REGULAR_USER_SHADOW,
    CRYPTOHOME_DEV_REGEX_REGULAR_USER_EPHEMERAL)
CRYPTOHOME_DEV_REGEX_GUEST = r'^guestfs$'

CRYPTOHOME_FS_REGEX_ANY = r'.*'
CRYPTOHOME_FS_REGEX_TMPFS = r'^tmpfs$'

CRYPTOHOME_MOUNT_PT = USER_DATA_DIR + '/user'

CRYPTOHOMED_LOG = '/var/log/cryptohomed.log'

# Directories to copy out of cryptohome, relative to CRYPTOHOME_MOUNT_PT.
CRYPTOHOME_DIRS_TO_RECOVER = ['crash', 'log']

DISABLE_BROWSER_RESTART_MAGIC_FILE = '/var/run/disable_chrome_restart'
DEFAULT_OWNERSHIP_TIMEOUT = 300  # Ownership is an inherently random process.

ENABLE_BROWSER_HANG_DETECTION_FILE = \
    '/var/run/session_manager/enable_hang_detection'

FLIMFLAM_TEST_PATH = '/usr/lib/flimflam/test/'

KEYGEN = 'keygen'

LOGGED_IN_MAGIC_FILE = '/var/run/state/logged-in'

LOGIN_PROFILE = USER_DATA_DIR + '/Default'
LOGIN_ERROR = 'Error=BadAuthentication'
LOGIN_PROMPT_VISIBLE_MAGIC_FILE = '/tmp/uptime-login-prompt-visible'
LOGIN_TRUST_ROOTS = '/etc/login_trust_root.pem'

MOCK_OWNER_CERT = 'mock_owner_cert.pem'
MOCK_OWNER_KEY = 'mock_owner_private.key'
MOCK_OWNER_POLICY = 'mock_owner.policy'

NETWORK_MANAGER = 'flimflam'

ISSUE_AUTH_TOKEN_URL = '/accounts/IssueAuthToken'
ISSUE_AUTH_TOKEN_NEW_URL = '/IssueAuthToken'

OAUTH1_GET_REQUEST_TOKEN_URL = '/accounts/o8/GetOAuthToken'
OAUTH1_GET_REQUEST_TOKEN_NEW_URL = '/o/oauth/GetOAuthToken/'
OAUTH1_GET_ACCESS_TOKEN_URL = '/accounts/OAuthGetAccessToken'
OAUTH1_GET_ACCESS_TOKEN_NEW_URL = '/OAuthGetAccessToken'
OAUTH_LOGIN_URL = '/accounts/OAuthLogin'
OAUTH_LOGIN_NEW_URL = '/OAuthLogin'
MERGE_SESSION_URL = '/MergeSession'

OAUTH2_CLIENT_ID = '77185425430.apps.googleusercontent.com'
OAUTH2_CLIENT_SECRET = 'OTJgUOQcT7lO7GsGZq2G4IlT'
OAUTH2_WRAP_BRIDGE_URL = '/accounts/OAuthWrapBridge'
OAUTH2_WRAP_BRIDGE_NEW_URL = '/OAuthWrapBridge'
OAUTH2_GET_AUTH_CODE_URL = '/o/oauth2/programmatic_auth'
OAUTH2_GET_TOKEN_URL = '/o/oauth2/token'

OWNER_KEY_FILE = WHITELIST_DIR + '/owner.key'

PORTAL_CHECK_URL = '/generate_204'

SERVICE_LOGIN_URL = '/accounts/ServiceLogin'
SERVICE_LOGIN_NEW_URL = '/ServiceLogin'
SERVICE_LOGIN_AUTH_URL = '/ServiceLoginAuth'
SERVICE_LOGIN_AUTH_ERROR = 'The username or password you entered is incorrect.'

SESSION_MANAGER = 'session_manager'
SESSION_MANAGER_LOG = '/var/log/session_manager'
SIGNED_POLICY_FILE = WHITELIST_DIR + '/policy'
SPECIAL_CASE_DOMAIN = 'gmail.com'
USER_POLICY_DIR = '/var/run/user_policy'
USER_POLICY_KEY_FILENAME = 'policy.pub'

TOKEN_AUTH_URL = '/accounts/TokenAuth'
TOKEN_AUTH_NEW_URL = '/TokenAuth'

UI_LOG = '/var/log/ui/ui.LATEST'
UPDATE_ENGINE_LOG = '/var/log/update_engine.log'

WINDOW_MANAGER = 'chromeos-wm'

RESOLV_CONF_FILE = '/etc/resolv.conf'

PENDING_SHUTDOWN_PATH = '/var/lib/crash_reporter/pending_clean_shutdown'
UNCLEAN_SHUTDOWN_DETECTED_PATH = '/var/run/unclean-shutdown-detected'

FAKE_ROOT_CA_DIR = '/etc/fake_root_ca'
FAKE_NSSDB_DIR = FAKE_ROOT_CA_DIR + '/nssdb'
