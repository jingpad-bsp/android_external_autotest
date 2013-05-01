# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import tempfile

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import autotemp, error
from autotest_lib.client.cros import cros_ui, cryptohome
from autotest_lib.client.cros import cros_ownership_test, ownership


class login_OwnershipApi(cros_ownership_test.OwnershipTest):
    """Tests to ensure that the Ownership API works for a local device owner.
    """
    version = 1

    _tempdir = None

    def setup(self):
        os.chdir(self.srcdir)
        utils.make('OUT_DIR=.')


    def initialize(self):
        super(login_OwnershipApi, self).initialize()
        # Start clean.
        cros_ui.stop()
        cryptohome.remove_vault(self._testuser)
        cryptohome.mount_vault(self._testuser, self._testpass, create=True)

        # Make device already owned by self._testuser.
        ownership.use_known_ownerkeys(self._testuser)

        self._tempdir = autotemp.tempdir(unique_id=self.__class__.__name__)
        cros_ui.start()


    def __generate_temp_filename(self, dir):
        """Generate a guaranteed-unique filename in dir."""
        just_for_name = tempfile.NamedTemporaryFile(dir=dir, delete=True)
        basename = just_for_name.name
        just_for_name.close()  # deletes file.
        return basename


    def run_once(self):
        pkey = ownership.known_privkey()
        pubkey = ownership.known_pubkey()
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
        if retrieved_policy is None: raise error.TestFail('Policy not found')
        self.compare_policy_response(retrieved_policy,
                                     owner=self._testuser,
                                     guests=False,
                                     new_users=True,
                                     roaming=True,
                                     whitelist=(self._testuser, 'a@b.c'),
                                     proxies={ 'proxy_mode': 'direct' })
        try:
            # Sanity check against an incorrect policy
            self.compare_policy_response(retrieved_policy,
                                         owner=self._testuser,
                                         guests=True,
                                         whitelist=(self._testuser, 'a@b.c'),
                                         proxies={ 'proxy_mode': 'direct' })
        except ownership.OwnershipError:
            pass
        else:
            raise error.TestFail('Did not detect bad policy')

        try:
            cros_ui.restart()
        except error.TestError as e:
            logging.error(str(e))
            raise error.TestFail('Could not stop session for owner')


    def cleanup(self):
        cryptohome.unmount_vault()
        if self._tempdir: self._tempdir.clean()
        cros_ui.start(allow_fail=True)
        super(login_OwnershipApi, self).cleanup()
