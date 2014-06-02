# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, shutil, tempfile
from autotest_lib.client.bin import fio_util, test, utils
from autotest_lib.client.cros import cryptohome

TEST_USER = 'test@chromium.org'
TEST_PASSWORD = 'test'

class platform_CryptohomeFio(test.test):
    """Run FIO in the crypto partition."""

    version = 2

    def run_once(self, runtime, mount_cryptohome=True, tmpfs=False,
                 script=None, sysctls=None):
        if sysctls:
            for sysctl in sysctls:
                for key, val in sysctl.iteritems():
                    utils.sysctl(key, val)
        # Mount a test cryptohome vault.
        self.__mount_cryptohome = mount_cryptohome
        if mount_cryptohome:
            cryptohome.mount_vault(TEST_USER, TEST_PASSWORD, create=True)
            tmpdir = cryptohome.user_path(TEST_USER)
        else:
            if tmpfs:
                tmpdir = None
            else:
                tmpdir = self.tmpdir
        self.__work_dir = tempfile.mkdtemp(dir=tmpdir)

        results = {}
        # TODO make these parameters to run_once & check target disk for space.
        self.__filesize = '300m'
        self.__runtime = str(runtime)
        env_vars = ' '.join(
            ['FILENAME=' + os.path.join(self.__work_dir, script),
             'FILESIZE=' + self.__filesize,
             'RUN_TIME=' + self.__runtime
             ])
        job_file = os.path.join(self.bindir, script)
        results.update(fio_util.fio_runner(self, job_file, env_vars))
        self.write_perf_keyval(results)


    def cleanup(self):
        logging.info('Finished with FS stress, cleaning up.')
        if self.__mount_cryptohome:
            cryptohome.unmount_vault(TEST_USER)
            cryptohome.remove_vault(TEST_USER)
        else:
            shutil.rmtree(self.__work_dir)
