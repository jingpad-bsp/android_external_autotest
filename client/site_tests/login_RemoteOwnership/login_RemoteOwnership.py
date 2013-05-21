# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import random
import string
import os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import policy, session_manager
from autotest_lib.client.cros import cros_ui, cryptohome, ownership


class login_RemoteOwnership(test.test):
    """Tests to ensure that the Ownership API can be used, as an
       enterprise might, to set device policies.
    """

    version = 1

    _poldata = 'hooberbloob'

    def setup(self):
        os.chdir(self.srcdir)
        utils.make('OUT_DIR=.')


    def initialize(self):
        # Start with a clean slate wrt ownership
        cros_ui.stop()
        ownership.clear_ownership_files()
        cros_ui.start()
        super(login_RemoteOwnership, self).initialize()


    def run_once(self):
        sm = session_manager.connect()

        # Initial policy setup.
        priv = ownership.known_privkey()
        pub = ownership.known_pubkey()
        policy.push_policy_and_verify(
            policy.generate_policy(self.srcdir, priv, pub, self._poldata), sm)

        # Force re-key the device
        (priv, pub) = ownership.pairgen_as_data()
        policy.push_policy_and_verify(
            policy.generate_policy(self.srcdir, priv, pub, self._poldata), sm)

        # Rotate key gracefully.
        self.username = ''.join(random.sample(string.ascii_lowercase,6)) + "@foo.com"
        password = ''.join(random.sample(string.ascii_lowercase,6))
        cryptohome.remove_vault(self.username)
        cryptohome.mount_vault(self.username, password, create=True)

        (new_priv, new_pub) = ownership.pairgen_as_data()

        if not sm.StartSession(self.username, ''):
            raise error.TestFail('Could not start session for random user')

        policy.push_policy_and_verify(
            policy.generate_policy(self.srcdir,
                                   key=new_priv,
                                   pubkey=new_pub,
                                   policy=self._poldata,
                                   old_key=priv),
            sm)

        try:
            sm.StopSession('')
        except error.TestError as e:
            logging.error(str(e))
            raise error.TestFail('Could not stop session for random user')


    def cleanup(self):
        cryptohome.unmount_vault(self.username)
        super(login_RemoteOwnership, self).cleanup()
