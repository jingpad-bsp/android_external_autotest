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

    _tempdir = None

    def setup(self):
        os.chdir(self.srcdir)
        utils.make('OUT_DIR=.')


    def initialize(self):
        super(login_OwnershipApi, self).initialize()
        cros_ui.stop()
        cryptohome.remove_vault(self._testuser)
        cryptohome.mount_vault(self._testuser, self._testpass, create=True)
        # to prime nssdb.
        self._tempdir = autotemp.tempdir(unique_id=self.__class__.__name__)
        tmpname = self.__generate_temp_filename()
        utils.system_output(cros_ui.xcommand_as('HOME=%s %s %s' %
                                                (constants.CRYPTOHOME_MOUNT_PT,
                                                 constants.KEYGEN,
                                                 tmpname)))
        os.unlink(tmpname)

        self.use_known_ownerkeys()
        cros_ui.start()
        login.wait_for_browser()


    def __generate_temp_filename(self):
        just_for_name = tempfile.NamedTemporaryFile(mode='w', delete=True)
        basename = just_for_name.name
        just_for_name.close()  # deletes file.
        return basename


    def run_once(self):
        pkey = self.known_privkey()
        pubkey = self.known_pubkey()
        sm = self.connect_to_session_manager()
        if not sm.StartSession(self._testuser, ''):
            raise error.TestFail('Could not start session for owner')

        poldata = self.build_policy_data(owner=self._testuser,
                                         guests=False,
                                         new_users=True,
                                         roaming=True,
                                         whitelist=(self._testuser, 'a@b.c'),
                                         proxies={ 'proxy_mode': 'direct' })

        policy_string = self.generate_policy(pkey, pubkey, poldata)
        self.push_policy(policy_string, sm)
        retrieved_policy = self.get_policy(sm)

        if retrieved_policy != policy_string:
            raise error.TestFail('Policy should not be %s' % retrieved_policy)

        if not sm.StopSession(''):
            raise error.TestFail('Could not stop session for owner')


    def cleanup(self):
        cryptohome.unmount_vault()
        if self._tempdir: self._tempdir.clean()
        cros_ui.start(allow_fail=True)
        super(login_OwnershipApi, self).cleanup()
