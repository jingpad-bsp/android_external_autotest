# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Utility functions used for PKCS#11 library testing.

import logging, os, re, stat, pwd, grp

from autotest_lib.client.bin import utils
from autotest_lib.client.cros import constants

CRYPTOHOME_CMD = '/usr/sbin/cryptohome'
PKCS11_DIR = '/var/lib/opencryptoki'
PKCS11_TOOL = '/usr/bin/pkcs11-tool --module %s %s'
USER_TOKEN_NAME = 'User-Specific TPM Token'
USER_TOKEN_DIR= '/home/chronos/user/.tpm'


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
    expected_permissions = [
        ('/var/lib/opencryptoki', 'root:pkcs11', 0770),
        ('/var/lib/opencryptoki/tpm', 'root:pkcs11', 0770),
        ('/var/lib/opencryptoki/tpm/ipsec', 'root:root', 0777),
        ('/var/lib/opencryptoki/tpm/chronos', 'root:root', 0777),
        ('/var/lib/opencryptoki/tpm/root', 'root:root', 0777),
        ('/var/lib/opencryptoki/pk_config_data', 'chronos:pkcs11', 0664),
        ('/home/chronos/user/.tpm', 'chronos:pkcs11', 0750),
        ('/home/chronos/user/.tpm/TOK_OBJ', 'chronos:pkcs11', 0750),
        ('/home/chronos/user/.tpm/TOK_OBJ/20000000', 'chronos:pkcs11', 0640),
        ('/home/chronos/user/.tpm/TOK_OBJ/30000000', 'chronos:pkcs11', 0640),
        ('/home/chronos/user/.tpm/TOK_OBJ/00000000', 'chronos:pkcs11', 0640),
        ('/home/chronos/user/.tpm/TOK_OBJ/70000000', 'chronos:pkcs11', 0640),
        ('/home/chronos/user/.tpm/TOK_OBJ/OBJ.IDX', 'chronos:pkcs11', 0640),
        ('/home/chronos/user/.tpm/TOK_OBJ/10000000', 'chronos:pkcs11', 0640),
        ('/home/chronos/user/.tpm/TOK_OBJ/60000000', 'chronos:pkcs11', 0640),
        ('/home/chronos/user/.tpm/TOK_OBJ/50000000', 'chronos:pkcs11', 0640),
        ('/home/chronos/user/.tpm/TOK_OBJ/40000000', 'chronos:pkcs11', 0640),
        ('/home/chronos/user/.tpm/.isinitialized', 'chronos:pkcs11', 0644)]
        # This file does not always have the same permissions. Sometimes it's
        # 640, sometimes 660. I suspect there is a race condition as to whether
        # the file exists when cryptohome sets recursive permissions.
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
    """Check if the PKCS#11 token is initialized properly."""
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
    if not __verify_symlinks():
        logging.error('Symlinks required by PKCS#11 were not correctly setup!')
        verify_result = False

    return verify_result

def is_chaps_enabled():
    """Check if the Chaps PKCS #11 implementation is enabled."""
    enabled_magic_file = '/home/chronos/.enable_chaps'
    return os.path.exists(enabled_magic_file)
