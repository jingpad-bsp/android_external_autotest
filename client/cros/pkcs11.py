# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utility functions used for PKCS#11 library testing."""

import grp, logging, os, pwd, re, stat, sys, shutil, pwd, grp

from autotest_lib.client.bin import utils

USER_TOKEN_NAME = 'User-Specific TPM Token'
USER_CHAPS_DIR = '.chaps'
TMP_CHAPS_DIR = '/tmp/chaps'
CHAPS_DIR_PERM = 0750
CHAPS_SALT_PERM = 0600


def __run_cmd(cmd, ignore_status=False):
    """Runs a command and returns the output from both stdout and stderr."""
    return utils.system_output(cmd + ' 2>&1', retain_output=True,
                               ignore_status=ignore_status).strip()

def __get_token_paths():
    """Return a dict with a path for each PKCS #11 token currently loaded."""
    token_paths = []
    for line in __run_cmd('chaps_client --list').split('\n'):
        match = re.search(r'Slot \d+: (/.*)\s*$', line);
        if match:
            token_paths.append(match.group(1))
    return token_paths

def __get_pkcs11_file_list(token_path):
    """Return string with PKCS#11 file paths and their associated metadata."""
    find_args = '-printf "\'%p\', \'%u:%g\', 0%m\n"'
    file_list_output = __run_cmd('find %s ' % token_path + find_args)
    return file_list_output

def __verify_tokenname(token_path):
    """Verify that the TPM token name is correct."""
    token_list = __run_cmd('p11_replay --list_tokens')
    logging.error('token_list: ' + token_list)
    match = re.search(r'^Slot \d+: (.*)\s*$', token_list, flags=re.MULTILINE)
    if not match:
        logging.error('Could not read PKCS#11 token label!')
        return False
    token_label = match.group(1)
    # Accept the legacy token label.
    if token_label == USER_TOKEN_NAME:
        return True
    # The token label should be a canonicalized username which means we should
    # be able to map it to the token path. This will fail if the UTF-8 username
    # is more than 32 bytes in length and was truncated to form the PKCS #11
    # token label.
    if len(token_label) == 32:
        return True
    obfuscate_cmd = 'cryptohome --action=obfuscate_user --user=%s' % token_label
    expected_token_path = __run_cmd(obfuscate_cmd)
    if token_path != expected_token_path:
        logging.error('Wrong or empty label on the PKCS#11 Token (Got = %s',
                      token_label)
        return False
    return True

def __verify_permissions(token_path):
    """Verify that the permissions on the initialized token dir are correct."""
    # List of 3-tuples consisting of (path, user:group, octal permissions)
    # Can be generated (for example), by:
    # find /home/chronos/user/.chaps -printf "'%p', '%u:%g', 0%m\n"
    # for i in $paths; do echo \(\'$i\', $(stat --format="'%U:%G', 0%a" $i)\),;
    # done
    expected_permissions = [
        (token_path, 'chaps:chronos-access', CHAPS_DIR_PERM),
        ('%s/auth_data_salt' % token_path, 'root:root', CHAPS_SALT_PERM),
        ('%s/database' % token_path, 'chaps:chronos-access', CHAPS_DIR_PERM)]
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

def verify_pkcs11_initialized():
    """Checks if the PKCS#11 token is initialized properly."""
    token_path_list = __get_token_paths()
    if len(token_path_list) != 1:
        logging.error('Expecting a single signed-in user with a token.')
        return False

    verify_cmd = ('cryptohome --action=pkcs11_token_status')
    __run_cmd(verify_cmd)

    verify_result = True
    # Do additional sanity tests.
    if not __verify_tokenname(token_path_list[0]):
        logging.error('Verification of token name failed!')
        verify_result = False
    if not __verify_permissions(token_path_list[0]):
        logging.error('PKCS#11 file list:\n%s',
                      __get_pkcs11_file_list(token_path_list[0]))
        logging.error(
            'Verification of PKCS#11 subsystem and token permissions failed!')
        verify_result = False
    return verify_result

def load_p11_test_token(auth_data='1234'):
    """Loads the test token onto a slot.

    @param auth_data: The authorization data to use for the token.
    """
    utils.system('sudo chaps_client --load --path=%s --auth="%s"' %
                 (TMP_CHAPS_DIR, auth_data))

def change_p11_test_token_auth_data(auth_data, new_auth_data):
    """Changes authorization data for the test token.

    @param auth_data: The current authorization data.
    @param new_auth_data: The new authorization data.
    """
    utils.system('sudo chaps_client --change_auth --path=%s --auth="%s" '
                 '--new_auth="%s"' % (TMP_CHAPS_DIR, auth_data, new_auth_data))

def unload_p11_test_token():
    """Unloads a loaded test token."""
    utils.system('sudo chaps_client --unload --path=%s' % TMP_CHAPS_DIR)

def copytree_with_ownership(src, dst):
    """Like shutil.copytree but also copies owner and group attributes.
    @param src: Source directory.
    @param dst: Destination directory.
    """
    utils.system('cp -rp %s %s' % (src, dst))

def setup_p11_test_token(unload_user_tokens, auth_data='1234'):
    """Configures a PKCS #11 token for testing.

    Any existing test token will be automatically cleaned up.

    @param unload_user_tokens: Whether to unload all user tokens.
    @param auth_data: Initial token authorization data.
    """
    cleanup_p11_test_token()
    if unload_user_tokens:
        for path in __get_token_paths():
            utils.system('sudo chaps_client --unload --path=%s' % path)
    os.makedirs(TMP_CHAPS_DIR)
    uid = pwd.getpwnam('chaps')[2]
    gid = grp.getgrnam('chronos-access')[2]
    os.chown(TMP_CHAPS_DIR, uid, gid)
    os.chmod(TMP_CHAPS_DIR, CHAPS_DIR_PERM)
    load_p11_test_token(auth_data)
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
