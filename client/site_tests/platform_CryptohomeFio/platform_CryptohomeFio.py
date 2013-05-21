# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, shutil, tempfile, utils
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import login as site_login
from autotest_lib.client.cros import cryptohome as site_cryptohome
from autotest_lib.client.cros import constants as chromeos_constants

CRYPTOHOMESTRESS_START = '/tmp/cryptohomestress_begin'
CRYPTOHOMESTRESS_END = '/tmp/cryptohomestress_end'
TEST_USER = 'test@chromium.org'
TEST_PASSWORD = 'test'

class platform_CryptohomeFio(test.test):
    version = 1

    def setup(self):
        if not os.path.exists(self.srcdir):
            os.mkdir(self.srcdir)
        # Currently, it seems impossible for a client dep to specify deps.
        self.job.setup_dep(['fio'])


    def initialize(self):
        # Is it necessary to check for a previously bad state?
        if site_login.logged_in():
            site_login.attempt_logout()

        # Copy the binary deps to the client host.
        deps = ['libaio', 'fio']
        for dep in deps:
            dep_dir = os.path.join(self.autodir, 'deps', dep)
            self.job.install_pkg(dep, 'dep', dep_dir)
        # Cleanup/touch marker files.
        if os.path.exists(CRYPTOHOMESTRESS_END):
            os.unlink(CRYPTOHOMESTRESS_END)
        open(CRYPTOHOMESTRESS_START, 'w').close()


    def run_once(self, runtime, mount_cryptohome=True, tmpfs=False,
                 script=None):
        # Mount a test cryptohome vault.
        self.__mount_cryptohome = mount_cryptohome
        if mount_cryptohome:
            site_cryptohome.mount_vault(TEST_USER, TEST_PASSWORD, create=True)
            tmpdir = chromeos_constants.CRYPTOHOME_MOUNT_PT
        else:
            if tmpfs:
                tmpdir = None
            else:
                tmpdir = self.tmpdir
        self.__work_dir = tempfile.mkdtemp(dir=tmpdir)
        self.__script = script
        # TODO make these parameters to run_once & check target disk for space.
        self.__filesize = '150m'
        self.__runtime = str(runtime)
        env_vars = ' '.join(
            ['FILENAME=' + os.path.join(self.__work_dir, self.__script),
             'FILESIZE=' + self.__filesize,
             'RUN_TIME=' + self.__runtime,
             'LD_LIBRARY_PATH=' + os.path.join(self.autodir, 'deps/libaio/lib')
             ])
        fio_bin = os.path.join(self.autodir, 'deps/fio/src/fio')
        fio_opts = ''
        fio = ' '.join([env_vars, fio_bin, fio_opts,
                        os.path.join(self.bindir, self.__script)])
        #TODO: Call fio and collect / parse logs. See hardware_storageFio.
        status =  utils.run(fio)
        logging.info(status.stdout)


    def cleanup(self):
        logging.info('Finished with FS stress, cleaning up.')
        if self.__mount_cryptohome:
            site_cryptohome.unmount_vault(TEST_USER)
            site_cryptohome.remove_vault(TEST_USER)
        else:
            shutil.rmtree(self.__work_dir)
        open(CRYPTOHOMESTRESS_END, 'w').close()
        os.unlink(CRYPTOHOMESTRESS_START)
