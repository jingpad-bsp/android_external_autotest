# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import hashlib
import logging
import os
import pyudev
import tempfile

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory


REMOVABLE_PREFIX = 'removable:'


def _TryReadFile(path):
    '''
    Returns the contents of a file if it exists, else returns None.

    If 'config_path' starts with 'removable:', waits for a removable device
    containing the given file.  For example, 'removable:foo.params' will use the
    first file called 'foo.params' on a removable device such as a USB stick.
    '''
    if path.startswith(REMOVABLE_PREFIX):
        mounts = {}
        for line in open("/etc/mtab"):
            fields = line.split(' ')
            device_node = fields[0]
            mount_point = fields[1]
            mounts[device_node] = mount_point
        logging.debug('Mounts: %s' % mounts)

        context = pyudev.Context()
        path_on_device = path[len(REMOVABLE_PREFIX):].lstrip('/')
        for dev in context.list_devices(subsystem='block', DEVTYPE='partition'):
            if dev.parent and dev.parent.attributes.get('removable') == '1':
                # If it's already mounted, try first without mounting/unmounting
                # it.
                mounted_path = mounts.get(dev.device_node)
                if mounted_path:
                    try_path = os.path.join(
                        mounts[dev.device_node], path_on_device)
                    logging.debug(
                        'Using configuration file at %s '
                        '(on device %s; already mounted)' % (
                            try_path, dev.device_node))
                    if os.path.exists(try_path):
                        return open(try_path).read()

                # Try mounting the device and retrieving the file.
                tmp = tempfile.mkdtemp(prefix='removable.')
                try:
                    utils.system('sudo mount -o ro %s %s' % (
                            dev.device_node, tmp))
                    try_path = os.path.join(tmp, path_on_device)
                    if os.path.exists(try_path):
                        logging.debug('Using configuration file at %s '
                                      '(on device %s)' % (
                                try_path, dev.device_node))
                        return open(try_path).read()
                except error.CmdError as e:
                    logging.debug('Unable to mount %s (%s); skipping' % (
                            dev.device_node, e))
                    # Fall through and continue to try other devices.
                finally:
                    utils.system('sudo umount -l %s' % dev.device_node,
                                 ignore_status=True)
                    try:
                        os.rmdir(tmp)
                    except OSError as e:
                        logging.debug('Unable to remove %s: %s' % (tmp, e))
    else:
        if os.path.exists(path):
            return open(path).read()

    return None


class PluggableConfig(object):
    '''
    A pluggable configuration for a test.  May include, for example,
    frequency ranges to test or device calibration parameters.

    The configuration may be replaced at runtime by reading a file (e.g., from a
    USB stick).
    '''
    def __init__(self, default_config):
        self.default_config = default_config

    def Read(self, config_path=None, timeout=30):
        '''
        Reads and returns the configuration.

        Uses the default configuration if 'config_path' is None.

        If 'config_path' starts with 'removable:', waits for a removable device
        containing the given file.  For example, 'removable:foo.params' will use
        the first file called 'foo.params' on a removable device such as a USB
        stick.

        Args:
            config_path: (optional) Path to configuration file.
            timeout: Number of seconds to wait for the configuration file.
        '''
        if config_path:
            factory.console.info(
                'Waiting for test configuration file %r...', config_path)
            config_str = utils.poll_for_condition(
                lambda: _TryReadFile(config_path),
                timeout=timeout,
                sleep_interval=0.5,
                desc='Configuration file %r' % config_path)
            factory.console.info('Read test configuration file %r', config_path)
            logging.info('Configuration file %r: MD5=%s; contents="""%s"""',
                         config_path,
                         hashlib.md5(config_str).hexdigest(),
                         config_str)
            return eval(config_str)
        else:
            logging.info('Using default configuration %r', self.default_config)
            # Return a copy, just in case the caller changes it.
            return copy.deepcopy(self.default_config)
