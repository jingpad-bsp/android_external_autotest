# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import dbus.glib
import gobject
import logging
import os
import tempfile

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import autotemp, error
from autotest_lib.client.cros import constants, cros_ui, cryptohome, login
from autotest_lib.client.cros import cros_ownership_test, ownership


class login_OwnershipApi(cros_ownership_test.OwnershipTest):
    version = 1

    _testuser = 'cryptohometest@chromium.org'
    _testpass = 'testme'
    _poldata = 'policydata'

    _tempdir = None

    def setup(self):
        os.chdir(self.srcdir)
        utils.make('OUT_DIR=.')


    def initialize(self):
        super(login_OwnershipApi, self).initialize()
        cryptohome.remove_vault(self._testuser)
        cryptohome.mount_vault(self._testuser, self._testpass, create=True)
        self._tempdir = autotemp.tempdir(unique_id=self.__class__.__name__)
        # to prime nssdb.
        tmpname = self.__generate_temp_filename()
        cros_ui.xsystem_as('HOME=%s %s %s' % (constants.CRYPTOHOME_MOUNT_PT,
                                              constants.KEYGEN,
                                              tmpname))
        os.unlink(tmpname)


    def __generate_temp_filename(self):
        just_for_name = tempfile.NamedTemporaryFile(mode='w', delete=True)
        basename = just_for_name.name
        just_for_name.close()  # deletes file.
        return basename


    def run_once(self):
        (pkey, pubkey) = ownership.generate_and_register_keypair(self._testuser,
                                                                 self._testpass)
        sm = self.connect_to_session_manager()
        if not sm.StartSession(self._testuser, ''):
            raise error.TestFail('Could not start session for owner')
        self.push_policy(self.generate_policy(pkey, pubkey, self._poldata), sm)
        if not sm.StopSession(''):
            raise error.TestFail('Could not stop session for owner')


    def cleanup(self):
        cryptohome.unmount_vault()
        if self._tempdir: self._tempdir.clean()
        super(login_OwnershipApi, self).cleanup()
