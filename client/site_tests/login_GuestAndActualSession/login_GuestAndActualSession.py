# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import gobject, os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib.cros import policy, session_manager
from autotest_lib.client.cros import constants, cros_ui, cryptohome, ownership

from dbus.mainloop.glib import DBusGMainLoop

class login_GuestAndActualSession(test.test):
    """Ensure that the session_manager correctly handles ownership when a guest
       signs in before a real user.
    """
    version = 1

    def setup(self):
        os.chdir(self.srcdir)
        utils.make('OUT_DIR=.')


    def initialize(self):
        super(login_GuestAndActualSession, self).initialize()
        # Ensure a clean beginning.
        cros_ui.stop()
        ownership.clear_ownership_files()
        cros_ui.start()

        DBusGMainLoop(set_as_default=True)
        self._session_manager = session_manager.connect()
        self._listener = session_manager.SignalListener(gobject.MainLoop())
        self._listener.listen_for_new_key_and_policy()


    def run_once(self):
        owner = 'first_user@nowhere.com'

        cryptohome.mount_guest()
        if not self._session_manager.StartSession(constants.GUEST_USER, ''):
            raise error.TestFail('Could not start session for guest')

        cryptohome.ensure_clean_cryptohome_for(owner)
        if not self._session_manager.StartSession(owner, ''):
            raise error.TestFail('Could not start session for ' + owner)

        self._listener.wait_for_signals(desc='Device ownership complete.')

        # Ensure that the first real user got to be the owner.
        retrieved_policy = policy.get_policy(self._session_manager)
        if retrieved_policy is None: raise error.TestFail('Policy not found')
        policy.compare_policy_response(self.srcdir, retrieved_policy,
                                       owner=owner)


    def cleanup(self):
        cros_ui.start(allow_fail=True, wait_for_login_prompt=False)
