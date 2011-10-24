# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re
import common
import constants as chromeos_constants
from autotest_lib.client.bin import test, utils
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


def unmount_vault(user=None):
    """
    Unmount the directory. Once unmount-by-user is supported, the user
    parameter will name the target user. See crosbug.com/20778
    """
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


def current_mounted_vault(device=chromeos_constants.CRYPTOHOME_DEVICE_REGEX,
                          expected_mountpt=
                          chromeos_constants.CRYPTOHOME_MOUNT_PT,
                          allow_fail=False):
    mount_line = utils.system_output(
        'grep %s /proc/$(pgrep cryptohomed)/mounts' % expected_mountpt,
        ignore_status=allow_fail)
    mount_parts = mount_line.split()
    if len(mount_parts) > 0 and re.match(device, mount_parts[0]):
        return mount_parts[0]
    else:
        return None


def is_mounted(device=chromeos_constants.CRYPTOHOME_DEVICE_REGEX,
               expected_mountpt=chromeos_constants.CRYPTOHOME_MOUNT_PT,
               allow_fail=False):
    return None != current_mounted_vault(device=device,
                                         expected_mountpt=expected_mountpt,
                                         allow_fail=allow_fail)


def is_mounted_on_tmpfs(device = chromeos_constants.CRYPTOHOME_INCOGNITO,
                        expected_mountpt =
                            chromeos_constants.CRYPTOHOME_MOUNT_PT,
                        allow_fail = False):
    mount_parts = __get_mount_parts(device, allow_fail)
    return (len(mount_parts) > 2 and device == mount_parts[0] and
            'tmpfs' == mount_parts[2])


def canonicalize(credential):
    """Perform basic canonicalization of |email_address|

    Perform basic canonicalization of |email_address|, taking
    into account that gmail does not consider '.' or caps inside a
    username to matter.  It also ignores everything after a '+'.
    For example, c.masone+abc@gmail.com == cMaSone@gmail.com, per
    http://mail.google.com/support/bin/answer.py?hl=en&ctx=mail&answer=10313
    """
    if not credential:
      return None

    parts = credential.split('@')
    if len(parts) != 2:
      raise error.TestError('Malformed email: ' + credential)

    (name, domain) = parts
    name = name.partition('+')[0]
    if (domain == chromeos_constants.SPECIAL_CASE_DOMAIN):
        name = name.replace('.', '')
    return '@'.join([name, domain]).lower()

def user_path(user):
    return utils.system_output('cryptohome-path user %s' % user)

def system_path(user):
    return utils.system_output('cryptohome-path system %s' % user)
