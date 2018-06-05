# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import logging
import json
import os
import tempfile

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.cros_disks import CrosDisksTester


def try_remove(filename):
    try:
        os.remove(filename)
        return True
    except OSError:
        return False


class CrosDisksFuseTester(CrosDisksTester):
    """Common steps for all FUSE-based tests.
    """
    def __init__(self, test, test_configs):
        super(CrosDisksFuseTester, self).__init__(test)
        self._test_configs = test_configs

    def setup_test_case(self, config):
        pass

    def teardown_test_case(self, config):
        pass

    def verify_test_case(self, config, mount_result):
        pass

    def _test_case(self, config):
        logging.info('Testing "%s"', config['description'])
        self.setup_test_case(config)
        try:
            source = config['test_mount_source_uri']
            fstype = config.get('test_mount_filesystem_type')
            options = config.get('test_mount_options', [])
            expected_mount_completion = {
                'status': config['expected_mount_status'],
                'source_path': source,
            }
            if 'expected_mount_path' in config:
                expected_mount_completion['mount_path'] = \
                    config['expected_mount_path']

            self.cros_disks.mount(source, fstype, options)
            result = self.cros_disks.expect_mount_completion(
                    expected_mount_completion)
            try:
                self.verify_test_case(config, result)
            finally:
                self.cros_disks.unmount(source, ['lazy'])
        finally:
            self.teardown_test_case(config)

    def _run_all_test_cases(self):
        try:
            for config in self._test_configs:
                self._test_case(config)
        except RuntimeError:
            cmd = 'ls -la %s' % tempfile.gettempdir()
            logging.debug(utils.run(cmd))
            raise

    def get_tests(self):
        return [self._run_all_test_cases]


SSH_DIR_PATH = '/home/chronos/user/.ssh'
AUTHORIZED_KEYS = os.path.join(SSH_DIR_PATH, 'authorized_keys')
AUTHORIZED_KEYS_BACKUP = AUTHORIZED_KEYS + '.sshfsbak'


class CrosDisksSshfsTester(CrosDisksFuseTester):
    """A tester to verify sshfs support in CrosDisks.
    """
    def __init__(self, test, test_configs):
        super(CrosDisksSshfsTester, self).__init__(test, test_configs)

    def setup_test_case(self, config):
        if os.path.exists(AUTHORIZED_KEYS):
            # Make backup of the current authorized_keys
            utils.run('mv -f ' + AUTHORIZED_KEYS + ' ' + AUTHORIZED_KEYS_BACKUP,
                      ignore_status=True)

        pubkey, privkey = self._generate_keypair()
        self._register_key(pubkey)

        identity = base64.b64encode(privkey)
        known_hosts = base64.b64encode(self._generate_known_hosts())

        options = config.get('test_mount_options', [])
        options.append('IdentityBase64=' + identity)
        options.append('UserKnownHostsBase64=' + known_hosts)
        config['test_mount_options'] = options

    def teardown_test_case(self, config):
        if os.path.exists(AUTHORIZED_KEYS_BACKUP):
            # Restore authorized_keys from backup.
            utils.run('mv -f ' + AUTHORIZED_KEYS_BACKUP + ' ' + AUTHORIZED_KEYS,
                      ignore_status=True)

    def verify_test_case(self, config, mount_result):
        if 'expected_file' in config:
            f = config['expected_file']
            if not os.path.exists(f):
                raise error.TestFail('Expected file "' + f + '" not found')

    def _generate_keypair(self):
        f, keyfile = tempfile.mkstemp()
        os.close(f)
        try_remove(keyfile)
        try_remove(keyfile + '.pub')
        utils.run('ssh-keygen -b 2048 -t rsa -f "' + keyfile + '" -q -N ""')
        with open(keyfile, 'rb') as f:
            privkey = f.read()
        with open(keyfile + '.pub', 'rb') as f:
            pubkey = f.read()
        try_remove(keyfile)
        try_remove(keyfile + '.pub')
        return (pubkey, privkey)

    def _register_key(self, pubkey):
        utils.run('sudo -u chronos mkdir -p ' + SSH_DIR_PATH,
                  ignore_status=True)
        utils.run('sudo -u chronos touch ' + AUTHORIZED_KEYS)
        with open(AUTHORIZED_KEYS, 'wb') as f:
            f.write(pubkey)
        utils.run('sudo -u chronos chmod 0600 ' + AUTHORIZED_KEYS)

    def _generate_known_hosts(self):
        hostkey = '/mnt/stateful_partition/etc/ssh/ssh_host_ed25519_key.pub'
        with open(hostkey, 'rb') as f:
            keydata = f.readline().split()
        return 'localhost {} {}\n'.format(keydata[0], keydata[1])


class platform_CrosDisksSshfs(test.test):
    version = 1

    def run_once(self, *args, **kwargs):
        test_configs = []
        config_file = '%s/%s' % (self.bindir, kwargs['config_file'])
        with open(config_file, 'rb') as f:
            test_configs.extend(json.load(f))

        tester = CrosDisksSshfsTester(self, test_configs)
        tester.run(*args, **kwargs)
