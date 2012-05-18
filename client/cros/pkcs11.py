# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Utility functions used for PKCS#11 library testing.

import grp, logging, os, pwd, re, stat, sys, shutil, pwd, grp

import common, constants
from autotest_lib.client.bin import utils

CRYPTOHOME_CMD = '/usr/sbin/cryptohome'
PKCS11_DIR = '/var/lib/opencryptoki'
PKCS11_TOOL = '/usr/bin/pkcs11-tool --module %s %s'
USER_TOKEN_NAME = 'User-Specific TPM Token'
USER_TOKEN_DIR = '/home/chronos/user/.tpm'
USER_CHAPS_DIR = '/home/chronos/user/.chaps'
SYSTEM_CHAPS_DIR = '/var/lib/chaps'
TMP_CHAPS_DIR = '/tmp/chaps'
CHAPS_DIR_PERM = 0750


def __run_cmd(cmd, ignore_status=False):
    return utils.system_output(cmd + ' 2>&1', retain_output=True,
                               ignore_status=ignore_status).strip()


def __get_pkcs11_file_list():
    """Return string with PKCS#11 file paths and their associated metadata."""
    find_args = '-printf "\'%p\', \'%u:%g\', 0%m\n"'
    file_list_output = __run_cmd('find %s ' % PKCS11_DIR + find_args)
    file_list_output += __run_cmd('find %s ' % USER_TOKEN_DIR + find_args)
    return file_list_output

def ensure_initial_state():
    """Make sure we start an initial starting state for each sub-test.

    This includes:
    - ensuring pkcsslotd is not running, if it is, it is killed.
    - ensuring chapsd is not running, if it is, it is killed.
    - waiting for and ensuring that the tpm is already owned.
    """
    utils.system('pkill -TERM pkcsslotd', ignore_status=True)
    utils.system('pkill -KILL pkcsslotd', ignore_status=True)
    utils.system('pkill -TERM chapsd', ignore_status=True)
    utils.system('pkill -KILL chapsd', ignore_status=True)

    if os.path.exists(constants.PKCS11_INIT_MAGIC_FILE):
        os.remove(constants.PKCS11_INIT_MAGIC_FILE)

    ensure_tpm_owned()


def init_pkcs11():
    """Request PKCS#11 initialization."""
    cmd = (CRYPTOHOME_CMD + ' --action=pkcs11_init')
    return __run_cmd(cmd)


def ensure_tpm_owned():
    """Request for and wait for the TPM to get owned."""
    take_ownership_cmd = (CRYPTOHOME_CMD + ' --action=tpm_take_ownership')
    wait_ownership_cmd = (CRYPTOHOME_CMD + ' --action=tpm_wait_ownership')
    __run_cmd(take_ownership_cmd)
    # Ignore errors if the TPM is not being in the process of being owned.
    __run_cmd(wait_ownership_cmd, ignore_status=True)

def __verify_tokenname():
    """Verify that the TPM token name is correct."""
    pkcs11_lib_path = 'libchaps.so'
    pkcs11_label_cmd = PKCS11_TOOL % (pkcs11_lib_path, '-L')
    pkcs11_cmd_output = __run_cmd(pkcs11_label_cmd)
    m = re.search(r"token label:\s+(.*)\s*$", pkcs11_cmd_output,
                  flags=re.MULTILINE)
    if not m:
        logging.error('Could not read PKCS#11 token label!')
        return False
    if m.group(1) != USER_TOKEN_NAME:
        logging.error('Wrong or empty label on the PKCS#11 Token (Expected = %s'
                      ', Got = %s', USER_TOKEN_NAME, m.group(1))
        return False
    return True


def __verify_nosensitive():
    """Verify no sensitive key files exist in the user's token directory."""
    sensitive_key_files = ['PUBLIC_ROOT_KEY.PEM', 'PRIVATE_ROOT_KEY.PEM']
    for f in sensitive_key_files:
        if os.access(os.path.join(USER_TOKEN_DIR, f), os.F_OK):
            logging.error('Found sensitive file: %s in %s', f,
                          USER_TOKEN_DIR)
            return False
    return True


def __verify_permissions():
    """Verify that the permissions on the initialized token dir are correct."""
    # List of 3-tuples consisting of (path, user:group, octal permissions)
    # Can be generated (for example), by:
    # find /var/lib/opencryptoki -printf "'%p', '%u:%g', 0%m\n"
    # for i in $paths; do echo \(\'$i\', $(stat --format="'%U:%G', 0%a" $i)\),;
    # done
    if is_chaps_enabled():
        expected_permissions = [
            ('/home/chronos/user/.chaps', 'chaps:chronos-access', 0750),
            ('/home/chronos/user/.chaps/auth_data_salt', 'root:root', 0600),
            ('/home/chronos/user/.chaps/database', 'chaps:chronos-access',
                0750)]
    else:
        expected_permissions = [
            ('/var/lib/opencryptoki', 'root:pkcs11', 0770),
            ('/var/lib/opencryptoki/tpm', 'root:pkcs11', 0770),
            ('/var/lib/opencryptoki/tpm/ipsec', 'root:root', 0777),
            ('/var/lib/opencryptoki/tpm/chronos', 'root:root', 0777),
            ('/var/lib/opencryptoki/tpm/root', 'root:root', 0777),
            ('/var/lib/opencryptoki/pk_config_data', 'chronos:pkcs11', 0664),
            ('/home/chronos/user/.tpm', 'chronos:pkcs11', 0750),
            ('/home/chronos/user/.tpm/TOK_OBJ', 'chronos:pkcs11', 0750),
            ('/home/chronos/user/.tpm/TOK_OBJ/20000000', 'chronos:pkcs11',
            0640),
            ('/home/chronos/user/.tpm/TOK_OBJ/30000000', 'chronos:pkcs11',
            0640),
            ('/home/chronos/user/.tpm/TOK_OBJ/00000000', 'chronos:pkcs11',
            0640),
            ('/home/chronos/user/.tpm/TOK_OBJ/70000000', 'chronos:pkcs11',
            0640),
            ('/home/chronos/user/.tpm/TOK_OBJ/OBJ.IDX', 'chronos:pkcs11',
            0640),
            ('/home/chronos/user/.tpm/TOK_OBJ/10000000', 'chronos:pkcs11',
            0640),
            ('/home/chronos/user/.tpm/TOK_OBJ/60000000', 'chronos:pkcs11',
            0640),
            ('/home/chronos/user/.tpm/TOK_OBJ/50000000', 'chronos:pkcs11',
            0640),
            ('/home/chronos/user/.tpm/TOK_OBJ/40000000', 'chronos:pkcs11',
            0640),
            ('/home/chronos/user/.tpm/.isinitialized', 'chronos:pkcs11', 0644)]
            # This file does not always have the same permissions. Sometimes
            # it's 640, sometimes 660. I suspect there is a race condition as to
            # whether the file exists when cryptohome sets recursive
            # permissions.
            #('/home/chronos/user/.tpm/NVTOK.DAT', 'root:pkcs11', 0660)
    for item in expected_permissions:
        path = item[0]
        (user, group) = item[1].split(':')
        perms = item[2]
        stat_buf = os.lstat(path)
        if not stat_buf:
            logging.error('Could not stat %s while checking for permissions.',
                          path)
            return False
        # Check ownership.
        path_user = pwd.getpwuid(stat_buf.st_uid).pw_name
        path_group = grp.getgrgid(stat_buf.st_gid).gr_name
        if path_user != user or path_group != group:
            logging.error('Ownership of %s does not match! Got = (%s, %s)'
                          ', Expected = (%s, %s)', path, path_user, path_group,
                          user, group)
            return False

        # Check permissions.
        path_perms = stat.S_IMODE(stat_buf.st_mode)
        if path_perms != perms:
            logging.error('Permissions for %s do not match! (Got = %s'
                          ', Expected = %s)', path, oct(path_perms), oct(perms))
            return False

    return True


def __verify_symlinks():
    """Verify that symlinks are setup correctly from PKCS11_DIR."""
    symlinks_src_list = ['tpm/chronos', 'tpm/ipsec', 'tpm/root']
    symlink_dest = USER_TOKEN_DIR

    for link in symlinks_src_list:
        symlink_to_test = os.path.join(PKCS11_DIR, link)
        if not stat.S_ISLNK(os.lstat(symlink_to_test).st_mode):
            logging.error('%s is not a symbolic link!', symlink_to_test)
            return False
        if os.readlink(symlink_to_test) != symlink_dest:
            logging.error('%s symlink does not point to %s', symlink_to_test,
                          symlink_dest)
            return False

    return True


def verify_pkcs11_initialized():
    """Checks if the PKCS#11 token is initialized properly."""
    verify_cmd = (CRYPTOHOME_CMD + ' --action=pkcs11_token_status')
    __run_cmd(verify_cmd)

    verify_result = True
    # Do additional sanity tests.
    if not __verify_tokenname():
        logging.error('Verification of token name failed!')
        verify_result = False
    if not __verify_nosensitive():
        logging.error('PKCS#11 file list:\n%s', __get_pkcs11_file_list())
        logging.error('Checking of leftover sensitive key files failed!')
        verify_result = False
    if not __verify_permissions():
        logging.error('PKCS#11 file list:\n%s', __get_pkcs11_file_list())
        logging.error(
            'Verification of PKCS#11 subsystem and token permissions failed!')
        verify_result = False
    if not is_chaps_enabled() and not __verify_symlinks():
        logging.error('Symlinks required by PKCS#11 were not correctly setup!')
        verify_result = False

    return verify_result

def is_chaps_enabled():
    """Checks if the Chaps PKCS #11 implementation is enabled."""
    return not os.path.exists('/home/chronos/.disable_chaps')

def load_p11_test_token():
    """Loads the test token onto a slot."""
    __run_cmd('sudo p11_replay --load --path=%s --auth="1234"' % TMP_CHAPS_DIR)

def unload_p11_test_token():
    """Unloads a loaded test token."""
    __run_cmd('sudo p11_replay --unload --path=%s' % TMP_CHAPS_DIR)

def copytree_with_ownership(src, dst):
    """ Like shutil.copytree but also copies owner and group attributes."""
    utils.system('cp -rp %s %s' % (src, dst))

def setup_p11_test_token(unload_user_token):
    """Configures a PKCS #11 token for testing.

    Any existing test token will be automatically cleaned up.

    Args:
        unload_user_token: Whether to unload the currently loaded user token.
    """
    cleanup_p11_test_token()
    if unload_user_token:
        __run_cmd('p11_replay --unload --path=%s' % USER_CHAPS_DIR)
    os.makedirs(TMP_CHAPS_DIR)
    uid = pwd.getpwnam('chaps')[2]
    gid = grp.getgrnam('chronos-access')[2]
    os.chown(TMP_CHAPS_DIR, uid, gid)
    os.chmod(TMP_CHAPS_DIR, CHAPS_DIR_PERM)
    load_p11_test_token()
    unload_p11_test_token()
    copytree_with_ownership(TMP_CHAPS_DIR, '%s_bak' % TMP_CHAPS_DIR)

def restore_p11_test_token():
    """Restores a PKCS #11 test token to its initial state."""
    shutil.rmtree(TMP_CHAPS_DIR)
    copytree_with_ownership('%s_bak' % TMP_CHAPS_DIR, TMP_CHAPS_DIR)

def get_p11_test_token_db_path():
    """Returns the test token database path."""
    return '%s/database' % TMP_CHAPS_DIR

def verify_p11_test_token():
    """Verifies that a test token is working and persistent."""
    output = __run_cmd('p11_replay --generate --replay_wifi',
                       ignore_status=True)
    if not re.search('Sign: CKR_OK', output):
        print >> sys.stderr, output
        return False
    unload_p11_test_token()
    load_p11_test_token()
    output = __run_cmd('p11_replay --replay_wifi --cleanup',
                       ignore_status=True)
    if not re.search('Sign: CKR_OK', output):
        print >> sys.stderr, output
        return False
    return True

def cleanup_p11_test_token():
    """Deletes the test token."""
    unload_p11_test_token()
    shutil.rmtree(TMP_CHAPS_DIR, ignore_errors=True)
    shutil.rmtree('%s_bak' % TMP_CHAPS_DIR, ignore_errors=True)

def verify_p11_token():
    """Verifies that a PKCS #11 token is able to generate key pairs and sign."""
    output = __run_cmd('p11_replay --generate --replay_wifi --cleanup',
                       ignore_status=True)
    return re.search('Sign: CKR_OK', output)

def wait_for_pkcs11_token():
    """Waits for the PKCS #11 token to be available.

    This should be called only after a login and is typically called immediately
    after a login.

    Returns:
        True if the token is available.
    """
    try:
        utils.poll_for_condition(
            lambda: utils.system('cryptohome --action=pkcs11_token_status',
                                 ignore_status=True) == 0,
            desc='PKCS #11 token.',
            timeout=300)
    except utils.TimeoutError:
        return False
    return True
