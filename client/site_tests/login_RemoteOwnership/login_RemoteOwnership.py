# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import random
import string
import os

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import (cryptohome, cros_ownership_test, cros_ui,
                                      ownership)


class login_RemoteOwnership(cros_ownership_test.OwnershipTest):
    """Tests to ensure that the Ownership API can be used, as an
       enterprise might, to set device policies.
    """

    version = 1

    _poldata = 'hooberbloob'

    def setup(self):
        os.chdir(self.srcdir)
        utils.make('OUT_DIR=.')


    def run_once(self):
        sm = self.connect_to_session_manager()

        # Initial policy setup.
        priv = ownership.known_privkey()
        pub = ownership.known_pubkey()
        self.push_policy(self.generate_policy(priv, pub, self._poldata), sm)

        # Force re-key the device
        (priv, pub) = ownership.pairgen_as_data()
        self.push_policy(self.generate_policy(priv, pub, self._poldata), sm)

        # Rotate key gracefully.
        username = ''.join(random.sample(string.ascii_lowercase,6)) + "@foo.com"
        password = ''.join(random.sample(string.ascii_lowercase,6))
        cryptohome.remove_vault(username)
        cryptohome.mount_vault(username, password, create=True)

        (new_priv, new_pub) = ownership.pairgen_as_data()

        if not sm.StartSession(username, ''):
            raise error.TestFail('Could not start session for random user')

        self.push_policy(self.generate_policy(key=new_priv,
                                              pubkey=new_pub,
                                              policy=self._poldata,
                                              old_key=priv),
                         sm)

        try:
            cros_ui.restart()
        except error.TestError as e:
            logging.error(str(e))
            raise error.TestFail('Could not stop session for random user')


    def cleanup(self):
        cryptohome.unmount_vault()
        super(login_RemoteOwnership, self).cleanup()
