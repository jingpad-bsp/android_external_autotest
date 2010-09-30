# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re, utils
from autotest_lib.client.bin import chromeos_constants, test
from autotest_lib.client.common_lib import error


CRYPTOHOME_CMD = '/usr/sbin/cryptohome'

class ChromiumOSError(error.InstallError):
    """Generic error for ChromiumOS-specific exceptions."""
    pass


def __run_cmd(cmd):
    return utils.system_output(cmd + ' 2>&1', retain_output=True,
                               ignore_status=True).strip()


def get_user_hash(user):
    """Get the hash for the test user account."""
    hash_cmd = CRYPTOHOME_CMD + ' --action=obfuscate_user --user=%s' % user
    return __run_cmd(hash_cmd)


def remove_vault(user):
    """Remove the test user account."""
    logging.debug('user is %s', user)
    user_hash = get_user_hash(user)
    logging.debug('Removing vault for user %s - %s' % (user, user_hash))
    cmd = CRYPTOHOME_CMD + ' --action=remove --force --user=%s' % user
    __run_cmd(cmd)
    # Ensure that the user directory does not exist
    if os.path.exists(os.path.join('/home/.shadow/', user_hash)):
        raise ChromiumOSError('Cryptohome could not remove the test user.')


def mount_vault(user, password, create=False):
    cmd = (CRYPTOHOME_CMD + ' --action=mount --user=%s --password=%s' %
           (user, password))
    if create:
        cmd += ' --create'
    __run_cmd(cmd)
    # Ensure that the user directory exists
    user_hash = get_user_hash(user)
    if not os.path.exists(os.path.join('/home/.shadow/', user_hash)):
        raise ChromiumOSError('Cryptohome vault not found after mount.')
    # Ensure that the user directory is mounted
    if not is_mounted(allow_fail=True):
        raise ChromiumOSError('Cryptohome created the user but did not mount.')


def test_auth(user, password):
    cmd = (CRYPTOHOME_CMD + ' --action=test_auth --user=%s --password=%s' %
           (user, password))
    return 'Authentication succeeded' in __run_cmd(cmd)


def unmount_vault():
    """Unmount the directory."""
    cmd = (CRYPTOHOME_CMD + ' --action=unmount')
    __run_cmd(cmd)
    # Ensure that the user directory is not mounted
    if is_mounted(allow_fail=True):
        raise ChromiumOSError('Cryptohome did not unmount the user.')


def __get_mount_parts(expected_mountpt=chromeos_constants.CRYPTOHOME_MOUNT_PT,
                      allow_fail = False):
    mount_line = utils.system_output(
        'grep %s /proc/$(pgrep cryptohomed)/mounts' % expected_mountpt,
        ignore_status = allow_fail)
    return mount_line.split()


def is_mounted(device=chromeos_constants.CRYPTOHOME_DEVICE_REGEX,
               expected_mountpt=chromeos_constants.CRYPTOHOME_MOUNT_PT,
               allow_fail=False):
    mount_line = utils.system_output(
        'grep %s /proc/$(pgrep cryptohomed)/mounts' % expected_mountpt,
        ignore_status=allow_fail)
    mount_parts = mount_line.split()
    return len(mount_parts) > 0 and re.match(device, mount_parts[0])


def is_mounted_on_tmpfs(device = chromeos_constants.CRYPTOHOME_INCOGNITO,
                        expected_mountpt =
                            chromeos_constants.CRYPTOHOME_MOUNT_PT,
                        allow_fail = False):
    mount_parts = __get_mount_parts(device, allow_fail)
    return (len(mount_parts) > 2 and device == mount_parts[0] and
            'tmpfs' == mount_parts[2])
